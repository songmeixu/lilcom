#include <math.h>
#include <stdint.h>
#include <assert.h>



/*
  Defines a region of memory underlying a Vector64 or Matrix64.  The
  data is not owned here.

  Conceptually, the data in `data` represents a floating point number,
  where each element should be multiplied by pow(2.0, exponent) to
  get the actual value.
 */
typedef struct {
  /*  number of elements in `data` */
  int dim;
  /* exponent defines what the data means as a floating point number
     (multiply data[i] by pow(2.0, exponent) to get the float value). */
  int exponent;
  /* size is a number >= 0 such that abs(data[x] < (1 << size))
     for all 0 <= x < dim.  Bound does not have to be tight (i.e.
     it's OK if size is a little larger than needed). */
  int size;

  /*  The underlying data.  Not owned here from a memory management point of view,
      but the framework does not expect any given memory location to be
      owned by more than one Region64. */
  int64_t *data;
} Region64;

typedef struct {
  /* `region` is the top-level memory region that owns this data... it's needed
     when the exponent changes, as it all has to be kept consistent (there is
     one exponent per memory region.) */
  Region64 *region;
  /* number of elements in the vector.  Must be > 0 for the Vector64 to be
     valid.. */
  int dim;
  /* stride.  must be != 0. */
  int stride;
  /* Pointer to the zeroth element. */
  int64_t *data;
} Vector64;

typedef struct {
  /* memory region that owns this data. */
  Region64 *region;
  /* number of rows in the matrix */
  int num_rows;
  /* number of columns in the matrix */
  int num_cols;
  /* Distance in elements between rows */
  int row_stride;
  /* column stride, i.e. distance in elements between columns i and i+1.  Would
   * normally be 1. WARNING: current code will crash if this is not 1,
   * since we haven't needed it to be != 1 yet. */
  int col_stride;
  /* pointer to element [0,0]. */
  int64_t *data;
} Matrix64;


typedef struct {
  /* exponent defines what the data means as a floating point number
     (multiply data by pow(2.0, exponent) to get the float value). */
  int exponent;
  /* size is *the smallest* number >= 0 such that abs(data[x] < (1 << size)). */
  int size;
  int64_t data;
} Scalar64;

typedef struct {
  Region64 *region;
  int64_t *data;
} Elem64;  /* Elem64 is like Scalar64 but it is part of an existing region. */


inline extern uint64_t FM_ABS(int64_t a) {
  return (uint64_t)(a > 0 ? a : -a);
}


/*
  Initializes a Region64.
     @param [in]  data    data underlying the region; should be an array of at least `dim` elements
     @param [in]  dim     number of elements in the region
     @param [in]  exponent   exponent with which to interpret whatever data is currently
                          in the region (i.e. it will be interpreted as that integer
                          number + 2^exponent).
     @param [in]  size_hint   caller's approximation to the `size` of the region,
                          meaning the smallest power of 2 >= 0 that is greater than all
                          the absolute values of elements of the region.
     @param [out] region   region  the region object to be created
 */
void InitRegion64(int64_t *data, int dim, int exponent, int size_hint, Region64 *region);


/**
   Zeros the contents of a `Region64`, setting the exponent and size to zero.
   Good to call occasionally if you keep a region around for a while, since otherwise
   if you only access it from sub-parts, the size can become larger than
   it needs to be.
 */
void ZeroRegion64(Region64 *region);


extern inline void InitVector64(Region64 *region, int dim, int stride, int64_t *data, Vector64 *vec) {
  vec->region = region;
  vec->dim = dim;
  vec->stride = stride;
  vec->data = data;
  assert(dim > 0 && dim <= region->dim && stride != 0 &&
         data >= region->data && data < region->data + region->dim &&
         data + ((dim-1)*stride) >= region->data &&
         data + ((dim-1)*stride) < region->data + region->dim);
}

extern inline void InitSubVector64(const Vector64 *src, int offset, int dim, int stride, Vector64 *dest) {
  assert(offset >= 0 && offset + (dim-1) * stride < src->dim && stride != 0 &&
         offset < dim && offset + (dim-1) * stride >= 0);
  dest->region = src->region;
  dest->dim = dim;
  dest->stride = stride * src->stride;
  dest->data = src->data + offset * src->stride;
}


/**
   Zeros the region's data, setting size and exponent to zero.
 */
void ZeroRegion64(Region64 *region);

extern inline void InitMatrix64(Region64 *region,
                                int num_rows, int row_stride,
                                int num_cols, int col_stride,
                                int64_t *data, Matrix64 *mat) {
  mat->region = region;
  mat->num_rows = num_rows;
  mat->row_stride = row_stride;
  mat->num_cols = num_cols;
  mat->col_stride = col_stride;
  // WARNING: col-stride must be 1 currently.
  assert(col_stride == 1);
  mat->data = data;
  // TODO: the following assertions would need to change
  // if we choose to allow negative row-stride and col-stride != 1.
  int max_offset = (num_rows-1) * row_stride + (num_cols-1) * col_stride;
  assert(num_rows > 0 && num_cols > 0 && col_stride == 1 &&
         row_stride >= num_cols * col_stride &&
         data >= region->data && data + max_offset <  region->data + region->dim);
}

/* Returns 1 if vectors overlap in memory, 0 if they do not.
   Caution: may return 1 for some vectors that do not really overlap,
   as the method is quite simple.
   CAUTION: not tested.  For now we insist on things being from
   different regions.
*/
int VectorsOverlap(const Vector64 *vec1, const Vector64 *vec2);

extern inline void InitElem64(Region64 *region, int64_t *data, Elem64 *elem) {
  elem->region = region;
  elem->data = data;
}


/* Shift the data elements right by this many bits and adjust the exponent so
   the number it represents is unchanged.
         @param [in] right_shift   A shift value >= 0
         @param [in,out] region   The region to be shifted
*/
void ShiftRegion64Right(int right_shift, Region64 *region);

/* Shift the data elements left by this many bits and adjust the exponent so
   the number it represents is unchanged.
         @param [in] left_shift   A shift value >= 0
         @param [in,out] region   The region to be shifted
*/
void ShiftRegion64Left(int left_shift, Region64 *region);

/* Shift the data right by this many bits, and adjust the exponent so
   the number it represents is unchanged. */
void ShiftScalar64Right(int right_shift, Scalar64 *scalar);

/* Shift the data left by this many bits, and adjust the exponent so
   the number it represents is unchanged.  This is present only
   for testing purposes. */
void ShiftScalar64Left(int left_shift, Scalar64 *scalar);

/* Copies data from `src` to `dest`; they must have the same dimension
   and be from different regions.
   CAUTION: this is not very optimal about sizes; it just assumes
   the "worst case" in terms of the src data we're seeing being the
   largest src data (for purposes of `size` estimation).
*/
void CopyVector64(const Vector64 *src, Vector64 *dest);

/* Updates the `size` field of `vec` to be accurate. */
void FixVector64Size(const Vector64 *vec);

/* like BLAS saxpy.  y := a*x + y.
   x and y must be from different regions.   */
void AddScalarVector64(const Scalar64 *a, const Vector64 *x, Vector64 *y);

/* Does y := a * x.   x and y must be from different regions. */
void SetScalarVector64(const Scalar64 *a, const Vector64 *x, Vector64 *y);

/* does y[i] += a for each element of y. */
void Vector64AddScalar(const Scalar64 *a, Vector64 *y);

/* does y[i] := a for each element of y. */
void Vector64SetScalar(const Scalar64 *a, Vector64 *y);


/* y := a * b.  It is OK if some of the pointer args are the same.  */
void MulScalar64(const Scalar64 *a, const Scalar64 *b, Scalar64 *y);

/* y := a + b.  It is OK if some of the pointer args are the same.  */
void AddScalar64(const Scalar64 *a, const Scalar64 *b, Scalar64 *y);


/* Sets the elements of this vector to zero.  Does touch the `size`
   or exponent.  Currently intended for use inside implementation functions.
 */
void ZeroVector64(Vector64 *a);

/* Sets the size for this region to the appropriate value.
   (See docs for the `size` member).  0 <= size_hint <= 63
   is a hint for what we think the size might be.
*/
void SetRegion64Size(int size_hint, Region64 *r);

inline void NegateScalar64(Scalar64 *a) { a->data *= -1; }

/* Sets this scalar to an integer. */
void InitScalar64FromInt(int64_t i, Scalar64 *a);


/*
  a[i] = value:
     Sets the i'th element of vector a to 'value'.  This is
   not the same as setting a->data[i] = value, because of the
   exponent.
     @param [in] i      The element of `value` to set, must be in [0..a->dim-1]
     @param [in] value  The value to set.  Exponents are not supported;
                        for that, manually create a Scalar64.
     @param [in] size_hint  A number in [0,63] that is the user's best
                        guess to the `size` of `value`.
     @para [out] a  The vector to set
 */
void CopyIntToVector64Elem(int i, int64_t value, int size_hint, Vector64 *a);


/* Computes dot product between two Vector64's:
   y := a . b */
void DotVector64(const Vector64 *a, const Vector64 *b, Scalar64 *y);

/* Computes matrix-vector product:
     y := M x.   Note: y must not be in the same region as x or m.
*/
void SetMatrixVector64(const Matrix64 *m, const Vector64 *x,
                       Vector64 *y);


/* Copies the data in the scalar to the `elem`. */
void CopyScalarToElem64(const Scalar64 *scalar, Elem64 *elem);

/* Does Y := a. */
void CopyElemToScalar64(const Elem64 *a, Scalar64 *y);

/* Copies the i'th element of `a` to y:   y = a[i] */
void CopyVectorElemToScalar64(const Vector64 *a, int i, Scalar64 *y);

/* Copies `s` to the i'th element of `a`:  a[i] = s. */
void CopyScalar64ToVectorElem(const Scalar64 *s, int i, Vector64 *a);

/* Sets an element of a vector to a scalar:  y[i] = a. */
void CopyFromScalar64(const Scalar64 *a, int i, Vector64 *y);

/* Multiplies 64-bit scalars.   the args do not have to be distinct
   objects. */
void MulScalar64(const Scalar64 *a, const Scalar64 *b, Scalar64 *y);

/* does: y := a.  Just copies all the elements of the struct. */
extern inline void CopyScalar64(const Scalar64 *a, Scalar64 *y) {
  y->size = a->size;
  y->exponent = a->exponent;
  y->data = a->data;
}

/* Computes the inverse of a 64-bit scalar: does b := 1.0 / a.  The pointers do
   not have to be different.  Will die with assertion or numerical exception if
   a == 0. */
void InvertScalar64(const Scalar64 *a, Scalar64 *b);

/* Adds two 64-bit scalars.
   does: y := a + b. The pointers do not have to be different. */
void AddScalar64(const Scalar64 *a, const Scalar64 *b, Scalar64 *y);



/* Subtracts two 64-bit scalars. Must all be different pointers.
   does: y := a - b. */
void SubtractScalar64(const Scalar64 *a, const Scalar64 *b, Scalar64 *y);

/*  Divides scalars:  y := a / b. */
void DivideScalar64(const Scalar64 *a, const Scalar64 *b, Scalar64 *y);

/* Does: y := 1.0 / a */
void InvertScalar64(const Scalar64 *a,  Scalar64 *y);

/* Convert to double- needed only for testing. */
double Scalar64ToDouble(const Scalar64 *a);

/* Converts element i of vector `vec` to double and returns it. */
double Vector64ElemToDouble(int i, const Vector64 *vec);



/* Returns nonzero if a and b are similar within a tolerance.  Intended mostly
   for checking code.*/
int Scalar64ApproxEqual(const Scalar64 *a, const Scalar64 *b, float tol);


/*
  Returns the smallest integer i >= 0 such that
  (1 << i) > value, or equivalently (since `value` is unsigned), that
  value >> i == 0

   @param [in] value  The value whose size we are testing.  CAUTION: this is
                    unsigned, so if you are starting with a signed value you
                    should probably put it through FM_ABS() first.
   @param [in] guess    May be any value in [0,63]; it is an error if it is outside that
                    range.  If it's close to the true value it will be faster.
 */
int FindSize(uint64_t value, int guess);