import cv2
import numpy as np
import shutil

from skimage.morphology import skeletonize
from sklearn import decomposition
from sort import *
import matplotlib.pyplot as plt
import torch
import time
from torchvision.io import read_image
from torchvision.utils import draw_bounding_boxes, draw_segmentation_masks, save_image
from image_recognition_ai import get_transform
from os.path import isfile, join, splitext
from utilities import video_converter, video_maker, NumpyQueue


class LarvaeTracker:
    def __init__(self, model, parent_dir, save_dir):
        self.model = model
        self.parent_dir = parent_dir
        self.save_dir = save_dir
        self.directory = "temp_frames"
        self.output = "temp_bounded_frames"

    def track_video(self, video_name, array_len=10, accuracy=0.9, display=False):
        """
        Tracks the flies in the video.
        :param accuracy: The prediction accuracy threshold to accept a larva
        :param video_name: Name of the video to be processed
        :param array_len: Length of tracking array
        :param display: Whether to display the frames or not
        :return:
        """

        model = self.model
        parent_dir = self.parent_dir
        save_dir = self.save_dir
        directory = self.directory
        output = self.output

        # Path
        frames_path = os.path.join(parent_dir, directory)
        if not os.path.exists(frames_path):
            os.mkdir(frames_path)

        output_path = os.path.join(parent_dir, output)
        if not os.path.exists(output_path):
            os.mkdir(output_path)

        fps = video_converter(os.path.join(parent_dir, video_name), frames_path + "/")

        tracker = Sort(iou_threshold=0.1)

        device = torch.device('cuda') if torch.cuda.is_available() else torch.device('cpu')
        colours = np.random.rand(32, 3)  # used only for display

        if display:
            plt.ion()
            fig = plt.figure()
            ax1 = fig.add_subplot(111, aspect='equal')

        image_paths = list(sorted(os.listdir(frames_path)))
        center_coords = NumpyQueue(max_size=array_len)
        rotation_angles = NumpyQueue(max_size=array_len)
        max_len = 32
        for image_path in image_paths:
            image = read_image(frames_path + "/" + image_path)
            eval_transform = get_transform(train=False)

            model.eval()
            with torch.no_grad():
                x = eval_transform(image)
                # convert RGBA -> RGB and move to device
                x = x[:3, ...].to(device)
                predictions = model([x, ])
                pred = predictions[0]

            image = (255.0 * (image - image.min()) / (image.max() - image.min())).to(torch.uint8)
            image = image[:3, ...]
            pred_boxes = pred["boxes"].long()
            output_image = draw_bounding_boxes(image, pred_boxes, colors="red")

            masks = (pred["masks"] > 0).squeeze(1)
            boxes = pred["boxes"].cpu().numpy()
            scores = pred["scores"].cpu().numpy()

            boxes = boxes[scores > accuracy]
            masks = masks[scores > accuracy, ...]
            scores = scores[scores > accuracy]

            output_image = draw_segmentation_masks(output_image, (pred["masks"] > 0.7).squeeze(1), alpha=0.5, colors="blue")

            if display:
                ax1.imshow(output_image.permute(1, 2, 0))
                plt.title(splitext(image_path)[0] + ' Tracked Targets')

            detections = np.column_stack((boxes, scores))
            numpy_masks = (masks.cpu().numpy() * 255).round().astype(np.uint8)
            mask_ids = np.arange(0, len(numpy_masks))
            track_larvae, mask_ids = tracker.update(dets=detections, mask_ids=mask_ids)
            boxes = []
            if len(track_larvae) > max_len:
                max_len = len(track_larvae)
            centers = list(np.full((max_len, 2), False))
            colour = []
            for d in track_larvae:
                d = d.astype(np.int32)
                if display:
                    ax1.add_patch(
                        patches.Rectangle((d[0], d[1]), d[2] - d[0], d[3] - d[1], fill=False, lw=3, ec=colours[d[4] % 32, :]))

                boxes.append([d[0], d[1], d[2], d[3]])
                centers[d[4] % max_len] = [(d[2] - d[0])/2, (d[3] - d[1])/2]
                colour.append(tuple((colours[d[4] % 32, :]*255).astype(np.int32)))
            boxes = torch.tensor(boxes)
            center_coords.put(centers)
            speeds = center_coords.speed()
            speeds_ordered = []
            labels = []

            angles = self._get_length_diff(numpy_masks[mask_ids])
            ordered_angles = list(np.full((max_len, 1), False).squeeze(1))
            for i, mask_id in enumerate(mask_ids):
                ordered_angles[mask_id] = angles[i]
            rotation_angles.put(ordered_angles)
            rotation_speeds = rotation_angles.speed()
            rotation_speeds = rotation_speeds[:np.max(mask_ids)+1]

            for d in track_larvae:
                speeds_ordered.append(speeds[round(d[4] % max_len)])
                labels.append(d[4])
            labels = [f"larvae: {label:.3f}  Speed {speed:.3f} Rotation speed {rotation_speed:.3f}" for label, speed, rotation_speed in zip(labels,  speeds_ordered, rotation_speeds)]
            output_image = draw_bounding_boxes(output_image, boxes, labels, colors=colour, width=3)

            save_image(output_image.float(), os.path.join(output_path + "/", image_path), normalize=True)
            if display:
                fig.canvas.flush_events()
                plt.draw()
                ax1.cla()

        video_maker(os.path.join(save_dir, splitext(video_name)[0] + "_tracked" + ".mp4"), output_path + "/", fps)
        shutil.rmtree(frames_path)
        shutil.rmtree(output_path)
        print("done")

    def _get_angles(self,masks, num_splits=2):
        """
        Skeletonizes the arrays
        :param num_splits:
        :param masks:
        :return:
        """
        display = False
        angles = []
        for mask in masks:
            if display:
                cv2.imshow("mask", mask)
                cv2.waitKey(0)

            skeleton_mask = skeletonize(mask)
            skeleton_mask_coords = np.argwhere(skeleton_mask > 0)

            # PCA
            pca = decomposition.PCA(n_components=2)
            pca.fit(skeleton_mask_coords)
            rotated_skeleton_mask_coords = pca.fit_transform(skeleton_mask_coords)

            skeleton_x, skeleton_y = np.split(rotated_skeleton_mask_coords, [-1], axis=1)

            # Reduce the axis
            skeleton_x = skeleton_x.squeeze(1)
            skeleton_y = skeleton_y.squeeze(1)

            skeleton_x_split = np.array_split(skeleton_x, num_splits)
            skeleton_y_split = np.array_split(skeleton_y, num_splits)
            angle = 0
            for split in range(len(skeleton_x_split)):
                M2 = np.polyfit(skeleton_x_split[split], skeleton_y_split[split], 1)[0]
                angle += (abs(np.arctan(M2)) * 180 / np.pi)
            angle = 180 - angle
            angles.append(angle)
        return np.array(angles)

    def _get_length_diff(self, masks):
        display = False
        length_diff = []
        for mask in masks:
            if display:
                cv2.imshow("mask", mask)
                cv2.waitKey(0)

            skeleton_mask = skeletonize(mask)
            skeleton_mask_coords = np.argwhere(skeleton_mask > 0)

            # PCA
            pca = decomposition.PCA(n_components=2)
            pca.fit(skeleton_mask_coords)
            rotated_skeleton_mask_coords = pca.fit_transform(skeleton_mask_coords)

            skeleton_x, skeleton_y = np.split(rotated_skeleton_mask_coords, [-1], axis=1)

            skeleton_x = skeleton_x.squeeze(1)
            skeleton_y = skeleton_y.squeeze(1)

            end_to_end = np.max(skeleton_x) - np.min(skeleton_x)
            length = len(rotated_skeleton_mask_coords)
            length_diff.append(end_to_end / length)
        return length_diff


if __name__ == "__main__":
    video_name = "test_12.h264"
    parent_dir = "larvae_tracking_videos/unprocessed_video/"
    save_dir = "larvae_tracking_videos/processed_video_test/"

    if torch.cuda.is_available():
        model_path = "ai_models/model_gpu.pth"
    else:
        model_path = "ai_models/model_cpu.pth"

    model = torch.load(model_path)

    larvae_tracker = LarvaeTracker(model, parent_dir, save_dir)
    larvae_tracker.track_video(video_name)