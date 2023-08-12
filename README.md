# 3DCityDB Blender Importer/Exporter
To connect PostgreSQL in Python and use this plugin, the package psycopg2 should be downloaded in blender. 
Therefore, run the following codes in blender Text editor.
If the installation process is successful, it can be seen in the system console of blender.
```python
import subprocess
import sys
import os
 
python_exe = os.path.join(sys.prefix, 'bin', 'python.exe')
target = os.path.join(sys.prefix, 'lib', 'site-packages')
subprocess.call([python_exe, '-m', 'ensurepip'])
subprocess.call([python_exe, '-m', 'pip', 'install', '--upgrade', 'pip'])
subprocess.call([python_exe, '-m', 'pip', 'install', '--upgrade', 'psycopg2-binary', '-t', target])
```
References: 
Working with PostgreSQL databases from Blender
https://b3d.interplanety.org/en/working-with-postgresql-database-from-blender/
# Natural Language Interface
To utilize this plugin, the package NLTK should be installed using the following code:
```python
import subprocess
import sys
import os
 
python_exe = os.path.join(sys.prefix, 'bin', 'python.exe')
target = os.path.join(sys.prefix, 'lib', 'site-packages')
subprocess.call([python_exe, '-m', 'ensurepip'])
subprocess.call([python_exe, '-m', 'pip', 'install', '--upgrade', 'pip'])
subprocess.call([python_exe, '-m', 'pip', 'install', '--upgrade', 'nltk', '-t', target])
```
After the installation of NLTK, some other packages should be downloaded.
```python
import nltk
nltk.download('all')
```
If you want to use these two plugins after running those statements, you should package these two \*.py files into zip files separately, and then open Blender, click Edit->Preferences->Addons->Install to install these plugins.
