import argparse
import sys
import os
import json
import logging
import requests
from PIL import Image

# ##################  INSTALLATION NOTE #######################
##############################################################

# pip install requests
# pip install pillow

###############################################################
###############################################################


# enable info logging.
logging.getLogger().setLevel(logging.INFO)


def maybe_download(image_url, image_dir):

    """Download the image if not already exist, return the location path"""
    file_name = image_url.split("/")[-1]
    file_path = os.path.join(image_dir, file_name)

    if os.path.exists(file_path):
        return file_path

    # Else download the image
    try:
        response = requests.get(image_url)
        if response.status_code == 200:
            with open(file_path, 'wb') as f:
                f.write(response.content)
                return file_path
        else:
            raise ValueError( "Not a 200 response")

    except Exception as e:
        logging.exception("Failed to download image at " + image_url + " \n" + str(e) + "\nignoring....")
        raise e


def get_xml_for_bbx(bbx_label, bbx_data, width, height):

    if len(bbx_data['points']) == 4:
        # Regular BBX has 4 points of the rectangle.
        xmin = width*min(bbx_data['points'][0][0], bbx_data['points'][1][0], bbx_data['points'][2][0], bbx_data['points'][3][0])
        ymin = height * min(bbx_data['points'][0][1], bbx_data['points'][1][1], bbx_data['points'][2][1],
                            bbx_data['points'][3][1])

        xmax = width * max(bbx_data['points'][0][0], bbx_data['points'][1][0], bbx_data['points'][2][0],
                           bbx_data['points'][3][0])
        ymax = height * max(bbx_data['points'][0][1], bbx_data['points'][1][1], bbx_data['points'][2][1],
                            bbx_data['points'][3][1])

    else:
        # OCR BBX format has 'x','y' in one point.
        # We store the left top and right bottom as point '0' and point '1'
        xmin = int(bbx_data['points'][0]['x']*width)
        ymin = int(bbx_data['points'][0]['y']*height)
        xmax = int(bbx_data['points'][1]['x']*width)
        ymax = int(bbx_data['points'][1]['y']*height)

    xml = "<object>\n"
    xml = xml + "\t<name>" + bbx_label + "</name>\n"
    xml = xml + "\t<pose>Unspecified</pose>\n"
    xml = xml + "\t<truncated>Unspecified</truncated>\n"
    xml = xml + "\t<difficult>Unspecified</difficult>\n"
    xml = xml + "\t<occluded>Unspecified</occluded>\n"
    xml = xml + "\t<bndbox>\n"
    xml = xml + "\t\t<xmin>" + str(xmin) + "</xmin>\n"
    xml = xml + "\t\t<xmax>" + str(xmax) + "</xmax>\n"
    xml = xml + "\t\t<ymin>" + str(ymin) + "</ymin>\n"
    xml = xml + "\t\t<ymax>" + str(ymax) + "</ymax>\n"
    xml = xml + "\t</bndbox>\n"
    xml = xml + "</object>\n"
    return xml


def convert_to_pascalvoc(dataturks_labeled_item, image_dir, xml_out_dir, txt_out_dir):

    """Convert a dataturks labeled item to pascalVOCXML string.
      Args:
        dataturks_labeled_item: JSON of one labeled image from dataturks.
        image_dir: Path to  directory to downloaded images (or a directory already having the images downloaded).
        xml_out_dir: Path to the dir where the xml needs to be written.
        txt_out_dir: Path to the dir where the txt files needs to be written
      Returns:
        None.
      Raises:
        None.
      """
    try:
        data = json.loads(dataturks_labeled_item)
        if len(data['annotation']) == 0:
            logging.info("Ignoring Skipped Item");
            return False;

        width = data['annotation'][0]['imageWidth']
        height = data['annotation'][0]['imageHeight']
        image_url = data['content']

        image_file_path = maybe_download(image_url, image_dir)

        with Image.open(image_file_path) as img:
            width, height = img.size

        image_file_name = image_file_path.split(os.path.sep)[-1]

        image_file_name_without_ext = image_file_name.split(".")[0]
        with open(dataset_split_txt_file__path, 'a+') as f:
            f.write(str(image_file_name_without_ext) + '\n')

        image_dir_folder_name = image_dir.split("/")[-1]

        xml = "<annotation>\n<folder>" + image_dir_folder_name + "</folder>\n"
        xml = xml + "<filename>" + image_file_name + "</filename>\n"
        xml = xml + "<path>" + image_file_path + "</path>\n"
        xml = xml + "<source>\n\t<database>Unknown</database>\n</source>\n"
        xml = xml + "<size>\n"
        xml = xml + "\t<width>" + str(width) + "</width>\n"
        xml = xml + "\t<height>" + str(height) + "</height>\n"
        xml = xml + "\t<depth>Unspecified</depth>\n"
        xml = xml + "</size>\n"
        xml = xml + "<segmented>Unspecified</segmented>\n"

        for bbx in data['annotation']:

            if not bbx:
                continue;

            # Pascal VOC only supports rectangles.
            if "shape" in bbx and bbx["shape"] != "rectangle":
                continue;

            bbx_labels = bbx['label']
            # handle both list of labels or a single label.
            if not isinstance(bbx_labels, list):
                bbx_labels = [bbx_labels]

            for bbx_label in bbx_labels:

                xml = xml + get_xml_for_bbx(bbx_label, bbx, width, height)

                # Store labeled image name and count against label in dict - to be stored to file later
                if bbx_label not in  img_object_count:
                    img_object_count[bbx_label] = {}

                images = img_object_count[bbx_label]
                found_img_name=False
                if images:
                    for temp_image_name, count in images.items():
                        if temp_image_name == image_file_name_without_ext:
                            count = count + 1
                            images[temp_image_name] = count
                            found_img_name=True
                            break

                if not found_img_name:
                    images[image_file_name_without_ext] = 1

        xml = xml + "</annotation>"

        # output to a file.
        xml_file_path = os.path.join(xml_out_dir, image_file_name + ".xml")
        with open(xml_file_path, 'w') as f:
            f.write(xml)

        return True

    except Exception as e:
        logging.exception("Unable to process item " + dataturks_labeled_item + "\n" + "error = " + str(e))
        return False


def main():

    # Make sure everything is setup.
    if not os.path.isdir(image_download_dir):
        logging.exception("Please specify a valid directory path to download images, " + image_download_dir + " doesn't exist")
        return

    if not os.path.isdir(pascal_voc_xml_dir):
        logging.exception("Please specify a valid directory path to write Pascal VOC xml files, " + pascal_voc_xml_dir + " doesn't exist")
        return

    if not os.path.exists(dataturks_JSON_FilePath):
        logging.exception(
            "Please specify a valid path to dataturks JSON output file, " + dataturks_JSON_FilePath + " doesn't exist")
        return

    if not os.path.isdir(pascal_voc_txt_dir):
        logging.exception(
            "Please specify a valid directory path to write Pascal VOC ImageSet Text files, " + pascal_voc_txt_dir + " doesn't exist")
        return

    global dataset_split
    if dataset_split not in ('train', 'val', 'test'):
        print("Split value not specified / incorrect split value provided, assuming train")
        dataset_split = 'train'

    lines = []
    with open(dataturks_JSON_FilePath, 'r') as f:
        lines = f.readlines()

    if not lines or len(lines) == 0:
        logging.exception(
            "Please specify a valid path to dataturks JSON output file, " + dataturks_JSON_FilePath + " is empty")
        return

    global dataset_split_txt_file__path
    dataset_split_txt_file__path = os.path.join(pascal_voc_txt_dir, dataset_split + ".txt")
    # Flush the file content, if it already exists
    with open(dataset_split_txt_file__path, 'w+') as f:
        f.write('')

    count = 0;
    success = 0
    global img_object_count
    img_object_count = {}
    for line in lines:
        status = convert_to_pascalvoc(line, image_download_dir, pascal_voc_xml_dir, pascal_voc_txt_dir)

        if status:
            success = success + 1

        count+=1;
        if count % 10 == 0:
            logging.info(str(count) + " items done ...")

    for label, label_details in img_object_count.items():

        label_txt_file_name = label + '_' + dataset_split
        label_txt_file_path = os.path.join(pascal_voc_txt_dir, label_txt_file_name + ".txt")

        with open(label_txt_file_path, 'w+') as f:
            for image_name, count in label_details.items():
                f.write(image_name + ' ' + str(count) + '\n')

    logging.info("Completed: " + str(success) + " items done, " + str(len(lines) - success)
                 + " items ignored due to errors or for being skipped items.")


def create_arg_parser():

    """"Creates and returns the ArgumentParser object."""
    parser = argparse.ArgumentParser(
        description='Converts Dataturks output JSON file for Image bounding box to Pascal VOC format.')

    parser.add_argument('dataturks_JSON_FilePath',
                        help='Path to the JSON file downloaded from Dataturks.')
    parser.add_argument('image_download_dir',
                        help='Path to the directory where images will be dowloaded(if not already found in the dir).')
    parser.add_argument('pascal_voc_xml_dir',
                        help='Path to the directory where Pascal VOC XML files will be stored.')
    parser.add_argument('pascal_voc_txt_dir',
                        help='Path to the directory where Pascal VOC ImageSet Text files will be stored.')
    parser.add_argument('--dataset_split',
                        help='Dataset split(train/val/test) for which data transformation is being performed.')

    return parser


if __name__ == '__main__':

    global dataturks_JSON_FilePath
    global image_download_dir
    global pascal_voc_xml_dir
    global pascal_voc_txt_dir
    global dataset_split

    arg_parser = create_arg_parser()
    parsed_args = arg_parser.parse_args(sys.argv[1:])

    # setup global values.
    dataturks_JSON_FilePath = parsed_args.dataturks_JSON_FilePath
    image_download_dir = parsed_args.image_download_dir
    pascal_voc_xml_dir = parsed_args.pascal_voc_xml_dir
    pascal_voc_txt_dir = parsed_args.pascal_voc_txt_dir
    dataset_split = parsed_args.dataset_split

    main()
