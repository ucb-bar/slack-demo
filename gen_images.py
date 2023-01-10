import torch
from torch import nn
import torchvision
import torchvision.transforms as transforms
from torch.utils.data import DataLoader
import numpy as np

from imagenet_classes import classes, to_imagenet_class

if torch.cuda.is_available():
    device = torch.device('cuda:0')
else:
    device = torch.device('cpu')

transform = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

audienceset = torchvision.datasets.ImageFolder(root='./audience_images/',
                                        transform=transform)

audienceloader = DataLoader(audienceset, batch_size=4,
                       shuffle=False, num_workers=1)

for images in audienceloader:
    audienceimages = images[0]
    break

audienceimages_nhwc = torch.clamp(audienceimages * 32.0, min=-128, max=127).int().permute([0,2,3,1])

def to_c_array(t):
    torch.set_printoptions(threshold=np.inf)
    result = str(t)
    result = result[len('tensor('):-len(', dtype=torch.int32)')]
    result = result.replace('[','{').replace(']','}')
    result = result.replace(' ', '').replace('\n', '')
    return result

with open("images.h", "w") as f:
    f.write("""#ifndef MOBILENET_IMAGES_H
#define MOBILENET_IMAGES_H

static const elem_t images[4][224][224][3] row_align(1) = """)

    f.write(to_c_array(audienceimages_nhwc))

    f.write(';\n\n#endif\n\n')
