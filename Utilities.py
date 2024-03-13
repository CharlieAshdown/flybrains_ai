from os import listdir
from os.path import isfile, join, splitext
import imageio.v2 as io
import rawpy


def file_combiner(file_roots, new_file_location):
    """
    Takes all the images within a list of files and combines them into one.
    :param file_roots: Array of roots to the file.
    :param new_file_location: Location to store all files.
    :return:
    """
    for mul, file_root in enumerate(file_roots):
        files = [f for f in listdir(file_root) if isfile(join(file_root, f))]
        for im_num, file in enumerate(files):
            image = io.imread(file_root+file)
            io.imsave(new_file_location + str("{:04d}".format(im_num+40*mul)) + splitext(file)[1],
                      image)

    return


def image_converter(original_folder, save_folder, new_format='.png', original_format=None,  title_multiplier=False,
                    raw_processing_args=None):
    """
    Mass converts images to a different type.
    :param original_folder: The path to take the images from.
    :param save_folder: The path to store the new images.
    :param new_format: Format to convert to.
    :param original_format: Format to convert from, defaults to None
    :param title_multiplier: Number to multiply the title of the image by.
           Defaults to false if not needed.
    :param raw_processing_args: Arguments from rawpy processing
    :return:
    """
    raw_formats = ['.dng', '.gpr', '.nef']
    only_files = [f for f in listdir(original_folder) if isfile(join(original_folder, f))]
    for im_num, path in enumerate(only_files):
        # For raw image processing
        if original_format in raw_formats or splitext(path)[1] in raw_formats:
            if not raw_processing_args:
                raw_processing_args = {
                    "no_auto_bright": True,
                    "output_bps": 16,
                    "demosaic_algorithm": rawpy.DemosaicAlgorithm(3),
                    "output_color": rawpy.ColorSpace(2),
                    "use_camera_wb": True}
            with rawpy.imread(original_folder + "/" + path) as raw:
                image = raw.postprocess(**raw_processing_args)
        elif original_format == splitext(path)[1] or not original_format:
            image = io.imread(path)
        else:
            return
        if not title_multiplier:
            io.imsave(save_folder + splitext(path)[0] + new_format, image)
        elif isinstance(title_multiplier, int):
            io.imsave(save_folder + str("{:04d}".format(im_num + len(only_files) * title_multiplier)) + new_format, image)


if __name__ == "__main__":

    images_roots = ["C:/Users/Charlie/Documents/samples/samples_29_02_2024/training/test_1_training/images/",
                    "C:/Users/Charlie/Documents/samples/samples_29_02_2024/training/test_2_training/images/",
                    "C:/Users/Charlie/Documents/samples/samples_29_02_2024/training/test_3_training/images/",
                    "C:/Users/Charlie/Documents/samples/samples_29_02_2024/training/test_4_training/images/",
                    "C:/Users/Charlie/Documents/samples/samples_29_02_2024/training/test_5_training/images/",
                    "C:/Users/Charlie/Documents/samples/samples_29_02_2024/training/test_6_training/images/",
                    "C:/Users/Charlie/Documents/samples/samples_29_02_2024/training/test_7_training/images/",
                    "C:/Users/Charlie/Documents/samples/samples_29_02_2024/training/test_8_training/images/",
                    "C:/Users/Charlie/Documents/samples/samples_29_02_2024/training/test_9_training/images/"]

    all_images = "C:/Users/Charlie/Documents/samples/samples_29_02_2024/training/all_training/images/"

    file_combiner(images_roots, all_images)
