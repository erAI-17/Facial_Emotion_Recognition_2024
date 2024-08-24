from PIL import Image, ImageOps
import numpy as np
import torch
import torchvision.transforms.v2 as transforms
from utils.args import args
import cv2
import dlib
        
ImageNet_mean = [0.485, 0.456, 0.406] 
ImageNet_std = [0.229, 0.224, 0.225]

Calder_Mendes_mean_RGB = [0.49102524485829907, 0.3618844398451173, 0.31640123102109985]
Calder_Mendes_std_RGB = [0.26517980798288976, 0.21546631829305746, 0.21493371251079485]
Calder_Mendes_mean_DEPTH = [0.3581094589547684, 0.3581094589547684, 0.3581094589547684]
Calder_Mendes_std_DEPTH = [0.08069561050494341, 0.08069561050494341, 0.08069561050494341]

class ToTensorUint16:
    def __call__(self, img): #receives PIL image in uint16
        # Convert image to numpy array
        img_np = np.array(img).astype(np.float32)
        
        # Scale the image to [0, 1] by dividing by 9785
        img_np = img_np / 9785.0
        
        # If the image is grayscale, add a channel dimension
        if len(img_np.shape) == 2:
            img_np = np.expand_dims(img_np, axis=-1)
            img_np = np.repeat(img_np, 3, axis=-1)
        
        # Convert to PyTorch tensor
        img_tensor = torch.from_numpy(img_np).permute(2, 0, 1)
        return img_tensor
    
def RGB_to_G(img):
    # Convert the image to grayscale
    grayscale_img = img.convert("L")
    
    # Convert the grayscale image back to a NumPy array
    grayscale_array = np.array(grayscale_img)
    
    # Stack the grayscale array to create a 3-channel image
    stacked_img = np.stack((grayscale_array,)*3, axis=-1)
    
    # Convert the stacked array back to an image
    stacked_img = Image.fromarray(stacked_img)
    
    return stacked_img

# Initialize dlib's face detector (HOG-based) and create the landmark predictor
detector = dlib.get_frontal_face_detector()
predictor = dlib.shape_predictor("./models/pretrained_models/shape_predictor_68_face_landmarks.dat")
def landmark_extraction(img):
    #convert image to numpy array
    img_np = np.array(img)
    fallback_scale=2
    original_shape = img_np.shape[:2]
    
       # Detect faces in the original image
    faces = detector(img_np)
    
    if len(faces) >= 1:
        face = faces[0]
    else:
        # Resize the image for fallback detection
        img_resized = cv2.resize(img_np, (original_shape[1] * fallback_scale, original_shape[0] * fallback_scale))
        faces = detector(img_resized)
        
        if len(faces) >= 1:
            face = faces[0]
            
            # Scale the face rectangle back to the original size
            face = dlib.rectangle(
                int(face.left() / fallback_scale),
                int(face.top() / fallback_scale),
                int(face.right() / fallback_scale),
                int(face.bottom() / fallback_scale)
            )
        else:
            print("No face detected even after resizing.")
            return img
    
    # Get landmarks
    landmarks = predictor(img_np, face)
    
    # Convert landmarks to a list of (x, y) tuples
    landmarks_list = [(p.x, p.y) for p in landmarks.parts()]
    
    # Draw landmarks on the image (optional)
    for (x, y) in landmarks_list:
        cv2.circle(img_np, (x, y), 2, (0, 255, 0), -1)
    
    # Convert back to PIL image
    img_with_landmarks = Image.fromarray(img_np)
    
    return img_with_landmarks
        
        
class RGBTransform:
    def __init__(self, augment=False):
        self.to_tensor = [
                transforms.ToImage(), 
                transforms.ToDtype(torch.float32, scale=True), #convert to float32 and scale to [0,1] (deviding by 255)
        ]
        
        self.resize = []    
        if args.models['RGB'].model == 'efficientnet_b2':
            self.resize = [transforms.Resize((260, 260), interpolation=transforms.InterpolationMode.BILINEAR),
            ]
        if args.models['RGB'].model == 'mobilenet_v4':
            self.resize = [transforms.Resize((256, 256), interpolation=transforms.InterpolationMode.BILINEAR),
            ]
            
        self.augment = []
        if augment:
            self.augment = [
            transforms.RandomHorizontalFlip(),
            transforms.RandomRotation(10),
            transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2, hue=0.1), 
            #transforms.GaussianBlur(kernel_size=(5, 9), sigma=(0.1, 5)), #simulates out of focus
            #transforms.RandomErasing(scale=(0.02, 0.25), ratio=(0.5, 2.0)), #simulates occlusions
            ]
            
        self.normalize = [
            transforms.Normalize(mean=Calder_Mendes_mean_RGB, std=Calder_Mendes_std_RGB),  # Normalize the tensor to [-1,1]
        ]
        
        self.transformations = self.to_tensor + self.resize + self.augment + self.normalize    
        self.transform = transforms.Compose(self.transformations)
            
    def __call__(self, img):    
        
        # if args.landmarks:
        #     img = landmark_extraction(img)
            
        #convert RGB to grayscale
        #img = RGB_to_G(img)
         
        # Apply transformations
        img = self.transform(img)
        
        return img
    
class DEPTHTransform:
    def __init__(self, augment=False):    
        
        self.to_tensor = [
            ToTensorUint16(),  # Converts the image to a tensor but doesn't normalize to [0,1]
        ]    
        
        self.resize = []
        if args.models['DEPTH'].model == 'efficientnet_b2':
            self.resize = [transforms.Resize((260, 260), interpolation=transforms.InterpolationMode.BILINEAR),
            ]
        if args.models['RGB'].model == 'mobilenet_v4':
            self.resize = [transforms.Resize((256, 256), interpolation=transforms.InterpolationMode.BILINEAR),
            ]
            
        self.augment = []
        if augment:
            self.augment = [
                transforms.RandomHorizontalFlip(),
                transforms.RandomRotation(10),
                #transforms.GaussianBlur(kernel_size=(5, 9), sigma=(0.1, 5)),
                #transforms.RandomErasing(scale=(0.02, 0.25), ratio=(0.5, 2.0)),
            ]
        
        self.normalize = [
            transforms.Normalize(mean=Calder_Mendes_mean_DEPTH, std=Calder_Mendes_std_DEPTH),
        ]
        
        self.transformations = self.to_tensor + self.resize + self.augment + self.normalize    
        self.transform = transforms.Compose(self.transformations)
    
    def __call__(self, img):            
        # Apply transformations
        img = self.transform(img)
        
        return img    
