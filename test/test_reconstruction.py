#!/usr/bin/python3
"""
Details about the Doument:
This script runs a test to compare lilcom's reconstruction accuracy
    and compare it with known MP3 bitrates. The script accepts additional
    arguments which by running `./test_reconstruction.py --help` all
    arguments are documented.
"""

# For parsing passed arguemtns, Built-in
import argparse
# Numpy library for array manipualtion, Required for Lilcom
import numpy as np
# Main package for audio compression and decompression, Principal
import lilcom
# For mathematic calculus, Built-in
import math
# For listing directories and os related tasks, Built-in
import os
# For loading wav audio to numpy array, Dependency
import scipy.io.wavfile
# For downsampling, Dependancy
import librosa
# For MP3 conversion, Dependancy
import pydub


defaultDatasetDir = "./OpenSLR81/samples"
defaultDataset = "OpenSLR81"
defaultDownloadLink = "http://www.openslr.org/resources/81/samples.tar.gz"


def PSNR(originalArray, reconstructedArray):
    """ This function calculates the peak signal to noise ratio between a
    signal and its reconstruction

       Args:
        originalArray: A numpy array which should be the original array
        before compression and reconstruction.
        reconstructedArray: A numpy array which in this case should be an
        array which is reconstructed from the compression function.
       Returns:
           A rational number which is the result of psnr between two given
    """
    # Convert both to float.
    if originalArray.dtype == np.int16:
        originalArray = originalArray.astype(np.float32) / 32768
    if reconstructedArray.dtype == np.int16:
        reconstructedArray = reconstructedArray.astype(np.float32) / 32768

    # Correct for any differences in dynamic range, which might be caused
    # by attempts of compression libraries like mp3 to avoid overflow.
    reconstructedArray *= np.sqrt((originalArray ** 2).sum() /
                                  (reconstructedArray ** 2).sum())

    max_value = float(np.max(np.abs(originalArray)))
    mean_square_error = (((originalArray - reconstructedArray) ** 2).sum() /
                         originalArray.size)
    if mean_square_error != 0:
        psnr = 20 * math.log10(max_value) - 10 * math.log10(mean_square_error)
    else:
        psnr = math.inf

    return psnr


def hash(array):
    return int(np.sum(np.abs(array))*2000) % int((2**16) - 1)


def logger(logmod="initialization", reportList=None):
    """ This function prints out the log given the initialization mode or
            the result of test on a single file. As a result it prints out
            the result on screen and in case that additional reports are
            requested it prints them out too.

       Args:
        logmod: There are two possible values, first is ``initialization''
            which is for the first line of the report. Also the other mode is
            the report mode in which an additional result list will be needed
            to be printed out.
        reportList: A list of dictionaries returned by the code, which is the
            evaluation result on one file.
    """
    global settings

    text = ""
    headerLine = ""
    if logmod == "initialization":
        text = "Reconstruction Test called for lilcom... \n"
        text += "The report is on the dataset placed at: " + \
                settings["dataset-dir"] + "\n"
        text += "The sample-rate is set to "
        if settings["sample-rate"] == 0:
            text += "the default sample rate of dataset"
        else:
            text += str(settings["sample-rate"])

        global evaulators

        headerLine += "filename" + "\t"
        for evaluator in evaulators:
            headerLine += \
                evaluator["algorithm"] + str(evaluator["additionalParam"]) + \
                "-bitrate"
            headerLine += "\t"
            headerLine += \
                evaluator["algorithm"] + str(evaluator["additionalParam"]) + \
                "-psnr"
            headerLine += "\t"
            headerLine += \
                evaluator["algorithm"] + str(evaluator["additionalParam"]) + \
                "-hash"
            headerLine += "\t"

        text += "\n"
        text += headerLine

    if logmod == "result":
        if reportList is None:
            return
        """
            Elements are each a dictionary of "evaluator" and "result"
        """
        text += reportList[0] + "\t"
        for element in reportList[1:]:
            elementResult = element["result"]
            text += str(elementResult["bitrate"])
            text += "\t\t"
            text += '%.2f' % elementResult["psnr"]
            text += "\t\t"
            text += str(elementResult["hash"])
            text += "\t\t"

    print(text)

    # Checks for output logfile settings
    if settings["release-log"] is not None:
        settings["release-log"].write(text)
        settings["release-log"].write("\n")

    if settings["release-df"]:
        if logmod == "initialization":
            settings["release-df"].write(headerLine.replace("\t", ","))
            settings["release-df"].write("\n")
        else:
            settings["release-df"].write(text.replace("\t", ","))
            settings["release-df"].write("\n")
    return


def lilcomReconstruct(audioArray, lpcOrder):
    """ This function will reconstruct the given audio array in form of a
            conescutive compression and decompression procedure.

       Args:
        audioArray: A numpy array as the audio signal
        lcpOrder: Same as lcpOrder in the main lilcom functions

       Returns:
           an Audio array with same size to the array passed as input which
            is a result of compresion and decompresion
    """
    bitPerSample = 6  # Issue make it passed by the operator
    # bitsPerSample Should be recieved from settings
    audioArray = audioArray.astype(np.float32)
    outputShape = list(audioArray.shape)

    outputShape[0] += 4
    outputShape = tuple(outputShape)

    outputArray = np.ndarray(outputShape, np.int8)
    reconstructedArray = np.ndarray(audioArray.shape, np.int16)

    c = lilcom.compress(audioArray, lpc_order=lpcOrder,
                        bits_per_sample=bitPerSample, axis=0)
    reconstructedArray = lilcom.decompress(c, dtype=audioArray.dtype)
    return reconstructedArray


def MP3Reconstruct(filename, bitrate):
    # Creating a temporary path for MP3 and reconstruction File
    tmpPath = "./ReconstTemp"
    if tmpPath[2:] in os.listdir("./"):
        os.system("rm -dR " + tmpPath)
    os.system("mkdir " + tmpPath)
    wavFile = pydub.AudioSegment.from_wav(filename)
    wavFile.export(tmpPath + "/output.mp3", format="mp3", bitrate=bitrate)
    # print("At bitrate {}, file {} compresses to {} bytes".format(
    #    bitrate, filename, os.path.getsize(tmpPath + "/output.mp3")))
    mp3File = pydub.AudioSegment.from_mp3(tmpPath + "/output.mp3")
    mp3File.export(tmpPath + "/reconst.wav", format="wav")
    sampleRateReconst, audioReconst = \
        scipy.io.wavfile.read(tmpPath + "/reconst.wav")
    os.system("rm -dR " + tmpPath)
    return audioReconst


def evaluate(filename=None, audioArray=None, algorithm="lilcom",
             additionalParam=None):
    """ This function does an evaluation on the given audio array, with
            the requested algorithm and additional parameters. As a result
            it returnes a map including the bitrate, a hash and the psnr
            result with the given audio array.

       Args:
        filename: The name of the file used for compression. It is requiered
            for some compression algorithms like MP3 which needs some file
            manipulations
        audioArray: Numpy array including original file. It is required for
            PSNR evaulation. If None value was passed, the function will
            load it from the passed filename.
        algorithm: The desired algorithm which will show which algorithm is
            chosen to be evaulated. Default value is set to lilcom
        additionalParam: Parameters which each algorithm is supposed to have.
            i.e. For lilcom it contains lpc-order and for MP3 it will have
            chosen bitrate.
       Returns:
            A dictionary with three keys; bitrate, psnr and hash.
    """
    global settings
    returnValue = dict.fromkeys(["bitrate", "psnr", "hash"])
    returnValue["bitrate"] = 0
    returnValue["psnr"] = 0
    returnValue["hash"] = 0

    """
    In case of empty input audio array it loads the array. The audio array is
        required for evaluation subroutine call 'PSNR'
    """
    if audioArray is None:
        if settings["sample-rate"] != 0:
            audioArray = waveRead(filename, settings["sample-rate"])
        if settings["sample-rate"] == 0:  # DOOOOO STH
            audioArray = waveRead(filename, settings["sample-rate"])
    reconstructedArray = None
    # Evaluation Procedure for lilcom
    if algorithm == "lilcom":
        reconstructedArray = lilcomReconstruct(audioArray,
                                               lpcOrder=additionalParam)
        returnValue["psnr"] = PSNR(audioArray, reconstructedArray)
        returnValue["bitrate"] = 8 * settings["sample-rate"]
        returnValue["hash"] = hash(reconstructedArray)
    # Evaluation Procedure for MP3
    elif algorithm == "MP3":
        reconstructedArray = MP3Reconstruct(filename,
                                            bitrate=additionalParam)
        returnValue["psnr"] = PSNR(audioArray, reconstructedArray)
        returnValue["bitrate"] = int(additionalParam[:3])*1000
        returnValue["hash"] = hash(reconstructedArray)
    # Evaluation for additional compression library
    else:
        pass

    return returnValue


def waveRead(filename, sampleRate=0):
    """ This function reads a wavefile at a desired sample rate and returns
            it in form of a numpy array

       Args:
        filename: The name of the file. File should be in wav format
            otherwise it will encounter error.
        sampleRate: an integer denoting the number of samples in a unit time.
            In case this is set to None, the function will choose the sample-
            -rate determined by arguemtns passed in while calling the script,
            otherwise the samplerate of the original wav file.

       Returns:
           a Numpy array of the given audio file.
    """
    audioArray = None
    if sampleRate == 0:
        sampleRate, audioArray = scipy.io.wavfile.read(filename)
        settings["sample-rate"] = sampleRate
        return audioArray
    if sampleRate != 0:
        sr, audioArray = scipy.io.wavfile.read(filename)
        if (sampleRate != sr):
            if audioArray.dtype == np.int16:
                audioArray = audioArray.astype(np.float32) / 32768
                downsampledArray = librosa.core.resample(
                                                audioArray.transpose(),
                                                sr, sampleRate).transpose()

            return downsampledArray
        return audioArray
    return None


# Parsing input arguments
parser = argparse.ArgumentParser(description="Lilcom reconstruction test \
            module")
parser.add_argument("--dataset", "-d",
                    help="The directory of test dataset")
parser.add_argument("--samplerate", "-s",
                    help="Number of samplings in a unit time for each audio")
parser.add_argument("--releaselog", "-l",
                    help="The name of the log file")
parser.add_argument("--releasedf", "-c",
                    help="The name of the csv file including results")
args = parser.parse_args()

# Global values for settings
settings = dict.fromkeys(["dataset-dir", "sample-rate", "release-log",
                         "release-df"])

# Assigning system values based on passed arguments
if args.dataset:
    settings["dataset-dir"] = args.dataset
else:
    if defaultDataset not in os.listdir():
        print("Downloading the dataset")
        os.system("mkdir ./" + defaultDataset)
        os.system("wget " + defaultDownloadLink + " -P ./" + defaultDataset)
        os.system("tar -xf ./" + defaultDataset + "/samples.tar.gz -C "
                  + defaultDataset)
        settings["dataset-dir"] = defaultDatasetDir
    else:
        settings["dataset-dir"] = defaultDatasetDir
if settings["dataset-dir"][-1] == "/":
    settings["dataset-dir"] = settings["dataset-dir"][:-1]
    # Removes the / if existing at the end of directory

if args.samplerate:
    settings["sample-rate"] = int(args.samplerate)
else:
    settings["sample-rate"] = 0

if args.releasedf:
    settings["release-df"] = args.releasedf
    csvOpener = open(settings["release-df"], "w+")
    settings["release-df"] = csvOpener
else:
    settings["release-df"] = None

if (args.releaselog):
    settings["release-log"] = args.releaselog
    fileOpener = open(settings["release-log"], "w+")
    settings["release-log"] = fileOpener

else:
    settings["release-log"] = None


evaulators = [
    {
        "algorithm": "lilcom",
        "additionalParam": 4
    },
    {
        "algorithm": "MP3",
        "additionalParam": "320k"
    },
    {
        "algorithm": "MP3",
        "additionalParam": "256k"
    },
    {
        "algorithm": "MP3",
        "additionalParam": "224k"
    },
    {
        "algorithm": "MP3",
        "additionalParam": "192k"
    },
    {
        "algorithm": "MP3",
        "additionalParam": "160k"
    }
]

fileList = [settings["dataset-dir"] + "/" + item
            for item in os.listdir(settings["dataset-dir"])
            if ".wav" in item]

# Initial prints
logger(logmod="initialization")

for file in fileList:
    audioArray = waveRead(file, settings["sample-rate"])

    fileEvaluationResultList = [os.path.basename(file)]
    for evaluator in evaulators:
        evaluationResult = evaluate(file, audioArray,
                                    evaluator["algorithm"],
                                    evaluator["additionalParam"])
        fileEvaluationResultList.append({"evaluator": evaluator,
                                        "result": evaluationResult})

    logger("result", fileEvaluationResultList)
