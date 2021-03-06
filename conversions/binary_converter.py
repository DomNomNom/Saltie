import io
import os
import struct

from conversions.input.input_formatter import get_state_dim
import numpy as np
import time
import logging

EMPTY_FILE = 'empty'
NO_FILE_VERSION = -1
NON_FLIPPED_FILE_VERSION = 0
FLIPPED_FILE_VERSION = 1
HASHED_NAME_FILE_VERSION = 2
IS_EVAL_FILE_VERSION = 3
BATCH_ARRAY_FILE_VERSION = 4
TIME_ADDITION_FILE_VERSION = 5


def get_latest_file_version():
    return TIME_ADDITION_FILE_VERSION


def write_array_to_file(game_file, array):
    bytes = convert_numpy_array(array)
    size_of_bytes = len(bytes.getvalue())
    game_file.write(struct.pack('i', size_of_bytes))
    game_file.write(bytes.getvalue())


def convert_numpy_array(numpy_array):
    """
    Converts a numpy array into compressed bytes
    :param numpy_array: An array that is going to be converted into bytes
    :return: A BytesIO object that contains compressed bytes
    """
    compressed_array = io.BytesIO()    # np.savez_compressed() requires a file-like object to write to
    np.save(compressed_array, numpy_array, allow_pickle=False, fix_imports=False)
    return compressed_array


def write_version_info(file, version_number):
    file.write(struct.pack('i', version_number))


def write_bot_hash(game_file, hashed_name):
    game_file.write(struct.pack('Q', hashed_name))


def write_is_eval(game_file, is_eval):
    game_file.write(struct.pack('?', is_eval))


def get_file_version(file):
    if not isinstance(file, io.BytesIO):
        file_name = os.path.basename(file.name).split('-')[0]
    else:
        file_name = 'ram'

    result = []

    try:
        chunk = file.read(4)
        file_version = struct.unpack('i', chunk)[0]
        if file_version > get_latest_file_version():
            file.seek(0, 0)
            file_version = NO_FILE_VERSION

        result.append(file_version)

        if file_version < HASHED_NAME_FILE_VERSION:
            result.append(file_name)
        else:
            chunk = file.read(8)
            hashed_name = struct.unpack('Q', chunk)[0]
            result.append(hashed_name)
        if file_version < IS_EVAL_FILE_VERSION:
            result.append(False)
        else:
            chunk = file.read(1)
            is_eval = struct.unpack('?', chunk)[0]
            result.append(is_eval)
    except Exception as e:
        result = [EMPTY_FILE, file_name, False]
        print('file version was messed up', e)
    finally:
        return tuple(result)


def get_file_size(f):
    # f is a file-like object.
    try:
        old_file_position = f.tell()
        f.seek(0, os.SEEK_END)
        size = f.tell()
        f.seek(old_file_position, os.SEEK_SET)
        return size
    except:
        return 0


def read_data(file, process_pair_function, batching=False):
    """
    Reads a file.  Quits if anything breaks.
    :param file: A simple python file object that will be read
    :param process_pair_function: A function that takes in an input array and an output array.
    There is also an optional number saying how many times this has been called for a single file.
    It always starts at 0
    :param batching: If more than one item in an array is read at the same time then we will batch
    them instead of doing them one at a time
    :return: None
    """

    file_version, hashed_name, is_eval = get_file_version(file)
    if file_version == EMPTY_FILE:
        return

    print('replay version:', file_version)
    # print('hashed name:', hashed_name)

    pair_number = 0
    totalbytes = 0
    total_time = 0
    counter = 0
    while True:
        try:
            start = time.time()
            chunk = file.read(4)
            if chunk == '':
                totalbytes += 4
                break
            input_array, num_bytes = get_array(file, chunk)
            totalbytes += num_bytes + 4
            chunk = file.read(4)
            if chunk == '':
                totalbytes += 4
                break
            output_array, num_bytes = get_array(file, chunk)
            total_time += time.time() - start
            batch_size = int(len(input_array) / get_state_dim())
            input_array = np.reshape(input_array, (batch_size, int(get_state_dim())))
            output_array = np.reshape(output_array, (batch_size, 8))
            if not batching:
                for i in range(len(input_array)):
                    process_pair_function(input_array[i], output_array[i], pair_number, hashed_name)
                    pair_number += 1
            else:
                process_pair_function(input_array, output_array, pair_number, hashed_name)
                pair_number += batch_size
            totalbytes += num_bytes + 4
            counter += 1
        except EOFError:
            #print('reached end of file')
            break
        except Exception as e:
            logging.exception('error occurred but not because of reading but something else')
    print('total batches [', counter, '] total pairs [', pair_number, ']')
    print('time reading', total_time)
    file_size = get_file_size(file)
    if file_size - totalbytes <= 4 + 4 + 8 + 1:
        pass
        # print('read: 100% of file')
    else:
        print('read: ' + str(totalbytes) + '/' + str(file_size) + ' bytes')


def get_array(file, chunk):
    """
    Gets a compressed numpy array from a file.

    Throws an EOFError if it has problems loading the data.

    :param file: The file that is being read
    :param chunk: A chunk representing a single number, this will be the number of bytes the array takes up.
    :return: A numpy array
    """
    try:
        starting_byte = struct.unpack('i', chunk)[0]
    except struct.error:
        #print('struct error')
        raise EOFError
    numpy_bytes = file.read(starting_byte)
    fake_file = io.BytesIO(numpy_bytes)
    try:
        result = np.load(fake_file, fix_imports=False)
    except OSError:
        print('numpy parse error')
        raise EOFError
    return result, starting_byte


def default_process_pair(input_array, output_array, pair_number):
    pass

