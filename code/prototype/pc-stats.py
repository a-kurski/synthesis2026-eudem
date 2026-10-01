import sys
import numpy as np
import pandas as pd

df = pd.read_csv(sys.argv[1], usecols=["translation_x", "translation_y", "translation_z"])
h = np.hypot(df.translation_x, df.translation_y)  # horizontal magnitude
v = df.translation_z                              # signed vertical

stats = {
    "RMSE":       lambda s: np.sqrt((s**2).mean()),
    "Mean":       lambda s: s.mean(),
    "Median abs": lambda s: s.abs().median(),
    "Min":        lambda s: s.abs().min(),
    "Max":        lambda s: s.abs().max(),
    "Stdev":      lambda s: s.std(),
}
for name, f in stats.items():
    print(f"{name:<11} H: {f(h):.4f}  V: {f(v):.4f}")
