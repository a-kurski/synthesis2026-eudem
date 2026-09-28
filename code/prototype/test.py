import numpy as np

np.set_printoptions(suppress=True)

affine = np.loadtxt("out-2.csv")
coords = [3.03333359e+05, 5.69082937e+06, 4.56110000e+01]

coords_h = np.hstack([coords, [1]])
transformed = (coords_h @ affine.T)[:3]

print("original coordinates are: \n", coords)
print("transformed coordinates are: \n", transformed)
