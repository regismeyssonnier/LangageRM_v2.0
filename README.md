# LangageRM_v2.0

## How to use it ?

1. Create the parser File with testc.bat.

2. Compile with ipython3 compile_rm.py exemple.rm

(3.) test.bat isn't the same like testc.bat, it creates the parser and interpret the langage file with test_rm.py(look at the command)

## How it works ?

It uses ANTLR for parser File and LLVM to create the code, and finally clang or gcc to create the .exe file

You have to install LLVM for windows and llvmlite for python.
