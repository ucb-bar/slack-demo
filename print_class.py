import sys
from imagenet_classes import classes, to_imagenet_class

for arg in sys.argv[1:]:
    print(classes[to_imagenet_class(int(arg))])

