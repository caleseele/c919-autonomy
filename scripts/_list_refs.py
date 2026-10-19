import os
refs = r"C:\Users\希儿\Projects\c919-autonomy\refs"
for n in sorted(os.listdir(refs)):
    if n.endswith('.obj') or n.endswith('.mtl'):
        print(repr(n), os.path.getsize(os.path.join(refs,n)))
