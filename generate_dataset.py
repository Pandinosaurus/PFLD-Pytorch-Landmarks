"""
Author: Amr Elsersy
email: amrelsersay@gmail.com
-----------------------------------------------------------------------------------
Description: 
"""

import os, time, enum
from PIL import Image
import argparse
import torch
import numpy as np 
import cv2
from euler_angles import EulerAngles

def parse_args():
    parser = argparse.ArgumentParser()
    args = parser.parse_args()
    return args


def rotate(image, landmarks, theta):
    return image, landmarks

def flip(image, landmarks):
    return image, landmarks

def scale(image, landmarks, factor):
    return image, landmarks

class Data_Augumentor:
    def __init__(self):
        self.face_shape = (112,112)
        self.theta1 = 15
        self.theta2 = 30
        self.euler_estimator = EulerAngles()

        self.root = 'data'
        self.train_path = os.path.join(self.root, 'train')
        self.test_path = os.path.join(self.root, 'test')
        try:
            os.mkdir(self.train_path)
            os.mkdir(self.test_path)
            os.mkdir(os.path.join(self.train_path, 'images'))
            os.mkdir(os.path.join(self.test_path, 'images'))           
            print('folders are created')
        except:
            print("train/test folders already exist")
            exit(0)

        self.images_root = os.path.join(self.root, 'WFLW', "WFLW_images")
        train_test_root = os.path.join(self.root, 'WFLW', "WFLW_annotations", "list_98pt_rect_attr_train_test")
        train_name = os.path.join(train_test_root, "list_98pt_rect_attr_train.txt")
        test_name = os.path.join(train_test_root, "list_98pt_rect_attr_test.txt")
        test_file  = open(test_name ,'r')
        train_file = open(train_name,'r')
        # the important ones
        self.test_lines  = test_file.read().splitlines()
        self.train_lines = train_file.read().splitlines()

    def scale_rect(self, rect, factor):
        (x1, y1), (x2, y2) = rect            
        rect_dw = (x2 - x1) * factor
        rect_dy = (y2 - y1) * factor
        x1 -= rect_dw/2
        x2 += rect_dw/2
        y1 -= rect_dy/2
        y2 += rect_dy/2
        x1 = max(x1, 0)
        x2 = max(x2, 0)
        y1 = max(y1, 0)
        y2 = max(y2, 0)
        rect[0] = (x1,y1)
        rect[1] = (x2,y2)
        return rect

    def generate_dataset(self, mode='train'):
        assert mode in ['train', 'test']
        lines = self.train_lines if mode == 'train' else self.test_lines
        save_path = self.train_path if mode == 'train' else self.test_path

        # annotation for all train/test dataset strings
        all_annotations_str = []

        k = 0
        for annotations_line in lines:
            # read annotations
            annotations = self.read_annotations(annotations_line)
            image_full_path = annotations['path']
            image = self.read_image(image_full_path)
            rect = annotations['rect']
            landmarks = annotations['landmarks']
            attributes = annotations['attributes']
            
            # crop face & resize to a bigger rect
            scaled_rect = self.scale_rect(rect, 0.2)
            # original_image, _, original_landmarks = self.crop_face(image, rect, landmarks)
            image, rect, landmarks = self.crop_face(image, scaled_rect, landmarks)
            
            # Data Augumentation
            all_images = []
            all_landmarks = []

            if mode == 'test':
                all_images = [image]
                all_landmarks = [landmarks]
            else:
                rotated_image1, rotated_landmarks1 = rotate(image, landmarks, self.theta1)
                rotated_image2, rotated_landmarks2 = rotate(image, landmarks, self.theta2)
                inverse_rotated_image1, inverse_rotated_landmarks1 = rotate(image, landmarks, -self.theta1)
                inverse_rotated_image2, inverse_rotated_landmarks2 = rotate(image, landmarks, -self.theta2)
                flip_image, flip_landmarks = flip(image, landmarks)

                all_images = [image, flip_image, rotated_image1, rotated_image2, 
                            inverse_rotated_image1, inverse_rotated_image2]
                all_landmarks = [landmarks, flip_landmarks, rotated_landmarks1, rotated_landmarks2, 
                                inverse_rotated_landmarks1, inverse_rotated_landmarks2]

            # for every augumented image
            for i, img in enumerate(all_images):
                img = all_images[i]
                landmark = all_landmarks[i]
                # generate euler angles from landmarks
                _, _, euler_angles = self.euler_estimator.eular_angles_from_landmarks(landmark)
                euler_str = ' '.join([str(round(angle,2)) for angle in euler_angles])

                # get image name
                new_image_path = self.save_image(img, image_full_path, i, save_path)

                # convert landmarks to string
                landmarks_list = landmark.reshape(196,).tolist()
                landmarks_str = ' '.join([str(l) for l in landmarks_list])

                # attributes list to string
                attributes_str = ' '.join([str(attribute) for attribute in attributes])

                # annotation string = image_name + 98 landmarks + attributes + euler
                new_annotation = ' '.join([new_image_path, landmarks_str, attributes_str, euler_str])
                all_annotations_str.append(new_annotation)
                # print(new_annotation)

            k += 1
            if k % 100 == 0:
                print(f'{mode} dataset: {k} generated data')
        one_annotation_str = '\n'.join([annotation for annotation in all_annotations_str])
        print(all_annotations_str)
        # ========= Save annotations ===============
        annotations_path = os.path.join(save_path, 'annotations.txt')
        annotations_file = open(annotations_path, 'w')
        annotations_file.write(one_annotation_str)
        annotations_file.close()
        print('*'*60,f'\n\t {mode} annotations is saved @ data/{mode}/annotations.txt')
        time.sleep(2)

    def save_image(self, img, full_name, id, save_path):
        full_name = full_name.split('/')
        image_name = full_name[-1][:-4] + '_' + str(id) + '.jpg'
        image_path = os.path.join(save_path, 'images', image_name)
        cv2.imwrite(image_path, img)
        return image_path

    def crop_face(self, image, rect, landmarks):
        (x1, y1), (x2, y2) = rect           
        # ROI
        image = image[int(y1):int(y2), int(x1):int(x2)]

        # resize the image & store the dims to resize landmarks
        h, w = image.shape[:2]
        image = cv2.resize(image, self.face_shape)
        new_h, new_w = self.face_shape

        # scale factor in x & y to scale the landmarks
        fx = new_w / w
        fy = new_h / h
        # translate the landmarks then scale them
        landmarks -= rect[0]
        for landmark in landmarks:
            landmark[0] *= fx
            landmark[1] *= fy

        # face rect
        rect[0] = (0,0)
        rect[1] = (x2-x1, y2-y1)

        return image, rect, landmarks

    def read_annotations(self, annotations):
        annotations = annotations.split(' ')

        landmarks = annotations[0:196]
        rect = annotations[196:200]        
        attributes = annotations[200:206]
        image_path = annotations[206]

        landmarks = [float(landmark) for landmark in landmarks]        
        landmarks = np.array(landmarks, dtype=np.float).reshape(98,2)
        rect = [float(coord) for coord in rect]
        rect = np.array(rect, dtype=np.float).reshape((2,2))

        return {
            'landmarks': landmarks,
            'rect' : rect,
            'attributes': attributes,
            'path': image_path
        }

    def read_image(self, name):
        path = os.path.join(self.images_root, name)
        image = cv2.imread(path, cv2.IMREAD_COLOR)
        return image        




def main():
    args = parse_args()
    augumentor = Data_Augumentor()
    augumentor.generate_dataset(mode='test')
    
if __name__ == "__main__":
    main()
