import os
import torch
from torchvision import models
import re
import cv2
import albumentations as A  # our data augmentation library
# remove arnings (optional)
import warnings
warnings.filterwarnings("ignore")
import time
from torchvision.utils import draw_bounding_boxes
from pycocotools.coco import COCO
# Now, we will define our transforms
from albumentations.pytorch import ToTensorV2
import shutil
import sys
from math import sqrt


# User parameters
SAVE_NAME_OD = "./Models-OD/Bolt_Vibrations-0.model"
DATASET_PATH = "./Training_Data/" + SAVE_NAME_OD.split("./Models-OD/",1)[1].split("-",1)[0] +"/"
IMAGE_SIZE              = int(re.findall(r'\d+', SAVE_NAME_OD)[-1] ) # Row and column number 
TO_PREDICT_PATH         = "./Images/Prediction_Images/To_Predict/"
PREDICTED_PATH          = "./Images/Prediction_Images/Predicted_Images/"
SAVE_ANNOTATED_IMAGES   = True
MIN_SCORE               = 0.7 # Default 0.5
WIDEN_TOGGLE            = False


def time_convert(sec):
    mins = sec // 60
    sec = sec % 60
    hours = mins // 60
    mins = mins % 60
    print("Time Lapsed = {0}h:{1}m:{2}s".format(int(hours), int(mins), round(sec) ) )


def deleteDirContents(dir):
    # Deletes photos in path "dir"
    # # Used for deleting previous cropped photos from last run
    for f in os.listdir(dir):
        full_path = os.path.join(dir, f)
        if os.path.isdir(full_path):
            shutil.rmtree(full_path)
        else:
            os.remove(full_path)


# Creates class folder
def makeDir(dir, classes_2):
    for classIndex, className in enumerate(classes_2):
        os.makedirs(dir + className, exist_ok=True)



# Starting stopwatch to see how long process takes
start_time = time.time()

# Deletes images already in "Predicted_Images" folder
deleteDirContents(PREDICTED_PATH)

dataset_path = DATASET_PATH



#load classes
coco = COCO(os.path.join(dataset_path, "train", "_annotations.coco.json"))
categories = coco.cats
n_classes_1 = len(categories.keys())
categories

classes_1 = [i[1]['name'] for i in categories.items()]



# lets load the faster rcnn model
model_1 = models.detection.fasterrcnn_resnet50_fpn(pretrained=True, 
                                                   box_detections_per_img=500,
                                                   min_size=720, # 1200 at work, 1700 at home
                                                   max_size=2500
                                                   )
in_features = model_1.roi_heads.box_predictor.cls_score.in_features # we need to change the head
model_1.roi_heads.box_predictor = models.detection.faster_rcnn.FastRCNNPredictor(in_features, n_classes_1)


# Loads last saved checkpoint
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

if torch.cuda.is_available():
    map_location=lambda storage, loc: storage.cuda()
else:
    map_location='cpu'

if os.path.isfile(SAVE_NAME_OD):
    checkpoint = torch.load(SAVE_NAME_OD, map_location=map_location)
    model_1.load_state_dict(checkpoint)

model_1 = model_1.to(device)

model_1.eval()
torch.cuda.empty_cache()

transforms_1 = A.Compose([
    # A.Resize(IMAGE_SIZE, IMAGE_SIZE), # our input size can be 600px
    # A.Rotate(limit=[90,90], always_apply=True),
    ToTensorV2()
])


# Start FPS timer
fps_start_time = time.time()

color_list =['green', 'red', 'blue', 'magenta', 'orange', 'cyan', 'lime', 'turquoise', 'yellow']
pred_dict = {}
for video_name in os.listdir(TO_PREDICT_PATH):
    video_path = os.path.join(TO_PREDICT_PATH, video_name)
    
    
    video_capture = cv2.VideoCapture(video_path)
    
    # Video frame count and fps needed for VideoWriter settings
    frame_count = int(video_capture.get(cv2.CAP_PROP_FRAME_COUNT))
    video_fps = round( video_capture.get(cv2.CAP_PROP_FPS) )
    
    # If successful and image of frame
    success, image_b4_color = video_capture.read()
    
    fourcc = cv2.VideoWriter_fourcc(*'MP4V')
    video_out = cv2.VideoWriter(PREDICTED_PATH + video_name, fourcc, video_fps, 
                                (int(image_b4_color.shape[1]), 
                                 int(image_b4_color.shape[0])
                                 )
                                )
    
    graph_x_list = []
    graph_y_list = []
    ii = 0
    count = 1
    while success:
        success, image_b4_color = video_capture.read()
        if not success:
            break
        
        # if count % 6 != 0:
        #     count += 1
        #     continue
        
        image = cv2.cvtColor(image_b4_color, cv2.COLOR_BGR2RGB)
        
        transformed_image = transforms_1(image=image)
        transformed_image = transformed_image["image"]
        
        if ii == 0:
            line_width = max(round(transformed_image.shape[1] * 0.002), 1)
        
        with torch.no_grad():
            prediction_1 = model_1([(transformed_image/255).to(device)])
            pred_1 = prediction_1[0]
        
        dieCoordinates = pred_1['boxes'][pred_1['scores'] > MIN_SCORE]
        die_class_indexes = pred_1['labels'][pred_1['scores'] > MIN_SCORE]
        # BELOW SHOWS SCORES - COMMENT OUT IF NEEDED
        die_scores = pred_1['scores'][pred_1['scores'] > MIN_SCORE]
        
        # labels_found = [str(int(die_scores[index]*100)) + "% - " + str(classes_1[class_index]) 
        #                 for index, class_index in enumerate(die_class_indexes)]
        labels_found = [str(classes_1[class_index]) 
                        for index, class_index in enumerate(die_class_indexes)]
        
        if WIDEN_TOGGLE:
            boxes_widened = dieCoordinates
            # Widens boxes
            for i in range(len(dieCoordinates)):
                box_width = dieCoordinates[i,2]-dieCoordinates[i,0]
                box_height = dieCoordinates[i,3]-dieCoordinates[i,1]
                
                # Width
                boxes_widened[i, 0] = max(dieCoordinates[i][0] - int(box_width/3), 0)
                boxes_widened[i, 2] = min(dieCoordinates[i][2] + int(box_width/3), transformed_image.shape[2])
                
                # Height
                boxes_widened[i, 1] = max(dieCoordinates[i][1] - int(box_height/3), 0)
                boxes_widened[i, 3] = min(dieCoordinates[i][3] + int(box_height/3), transformed_image.shape[1])
            
            dieCoordinates = boxes_widened
        
        if SAVE_ANNOTATED_IMAGES:
            predicted_image = draw_bounding_boxes(transformed_image,
                boxes = dieCoordinates,
                # labels = [classes_1[i] for i in die_class_indexes], 
                # labels = [str(round(i,2)) for i in die_scores], # SHOWS SCORE IN LABEL
                width = line_width,
                colors = [color_list[i] for i in die_class_indexes],
                font = "arial.ttf",
                font_size = 10
                )
            
            predicted_image_cv2 = predicted_image.permute(1,2,0).contiguous().numpy()
            predicted_image_cv2 = cv2.cvtColor(predicted_image_cv2, cv2.COLOR_RGB2BGR)
            
            for dieCoordinate_index, dieCoordinate in enumerate(dieCoordinates):
                
                # Finds center x and y coordinates for "Bolt" label bbox
                center_x = int(dieCoordinate[0] 
                                      + (dieCoordinate[2] - dieCoordinate[0])/2
                                      )
                center_y = int(dieCoordinate[1] 
                                      + (dieCoordinate[3] - dieCoordinate[1])/2
                                          )
                if count ==1:
                    center_x_orig = center_x
                    center_y_orig = center_y
                
                # Draws line from orig cirgle to center of bolt now
                cv2.line(predicted_image_cv2, 
                         pt1=(center_x_orig, center_y_orig), 
                         pt2=(center_x, center_y), 
                         color=(255,255,255), thickness=1
                         ) 
                
                # Draw circle over center of start image's bolt
                cv2.circle(predicted_image_cv2, 
                           center=(center_x_orig, center_y_orig), radius=5, 
                           color=(0,255,0), thickness=2, lineType=8, shift=0
                           )
                
                # Draw circle over center of bolt now
                cv2.circle(predicted_image_cv2, 
                           center=(center_x, center_y), radius=2, 
                           color=(255,0,255), thickness=2, lineType=8, shift=0
                           )
                
                start_point = ( int(dieCoordinate[0]), int(dieCoordinate[1]) )
                # end_point = ( int(dieCoordinate[2]), int(dieCoordinate[3]) )
                color = (255, 255, 255)
                # thickness = 3
                # cv2.rectangle(predicted_image_cv2, start_point, end_point, color, thickness)
                
                start_point_text = (start_point[0], max(start_point[1]-5,0) )
                font = cv2.FONT_HERSHEY_SIMPLEX
                fontScale = 1.0
                thickness = 2
                cv2.putText(predicted_image_cv2, labels_found[dieCoordinate_index], 
                            start_point_text, font, fontScale, color, thickness)
                
                # Draws frequency graph
                # -------------------------------------------------------------
                # Starting and end poitns of base of graph
                x_0 = int(transformed_image.shape[2]*.01)
                y_0 = int(transformed_image.shape[1]*.90)
                x_end = int(transformed_image.shape[2]*.99)
                
                # Draws lines in graph
                line_scale = 30
                for index in range(5):
                    if index == 0:
                        thickness = 2
                    else:
                        thickness = 1
                    cv2.line(
                        predicted_image_cv2, 
                        pt1=(x_0,  y_0-line_scale*index), 
                        pt2=(x_end, y_0-line_scale*index), 
                        color=(255,255,255), thickness=thickness
                        )
                
                # Calculates distance from center of original bolt image to now
                length_x = abs(center_x - center_x_orig)
                length_y = abs(center_y - center_y_orig)
                distance = int(sqrt( (length_x)**2 + (length_y)**2 )*line_scale)
                
                graph_x_list.append(x_0 + ii)
                graph_y_list.append(y_0 - distance)
                
                for index in range(len(graph_x_list)):
                    # Draw connecting dots of distance of center of 
                    #  bolt to original spot
                    cv2.line(
                        predicted_image_cv2, 
                        pt1=(graph_x_list[max(index-1,0)], graph_y_list[max(index-1,0)]), 
                        pt2=(graph_x_list[index], graph_y_list[index]), 
                        color=(255,255,255), thickness=1
                        ) 
                    cv2.circle(
                        predicted_image_cv2, 
                        center=(graph_x_list[index], graph_y_list[index]), 
                        radius=0, color=(255,0,255), thickness=2
                        )
                
                
                # -------------------------------------------------------------
            
            # Saves video with bounding boxes
            video_out.write(predicted_image_cv2)
        
        
        tenScale = 10
        ii += 1
        if ii % tenScale == 0:
            fps_end_time = time.time()
            fps_time_lapsed = fps_end_time - fps_start_time
            
            images_left = frame_count - ii
            time_left = images_left/(round(tenScale/fps_time_lapsed, 2)) # in seconds
            mins = time_left // 60
            sec = time_left % 60
            
            sys.stdout.write('\033[2K\033[1G')
            print("  " + str(ii) + " of " 
                  + str(frame_count), 
                  "-",  round(tenScale/fps_time_lapsed, 2), "FPS -",
                  "Time Left: {0}m:{1}s".format(int(mins), round(sec) ),
                  end="\r"
                  )
            fps_start_time = time.time()
        
        count += 1
        
    video_out.release()
    
    # Makes new line so that next class progress status can show in terminal/shell
    print("")

print("Done!")

# Stopping stopwatch to see how long process takes
end_time = time.time()
time_lapsed = end_time - start_time
time_convert(time_lapsed)