# LangageRM_v2.0

## How to use it ?

1. Create the parser File with testc.bat. (Only to create the new grammar file, if the RmLang*.* didn't exist). If you don't modify the grammar in*.g4 file skip to step 2).

2. Compile with ipython3 compile_rm.py exemple.rm (exemple.rm or another file *.rm). (Create your own program directly in rm files and compile in an exe file to execute the program.)

(3.) test.bat isn't the same like testc.bat, it creates the parser and interpret the langage file with test_rm.py(look at the command) OBSOLETE (it's just an example ANTLR)

Look at the wiki for more info.

## How it works ?

It uses ANTLR for parser File and LLVM to create the code, and finally clang or gcc to create the .exe file

You have to install LLVM for windows and llvmlite for python.

The **.rm files** are some example of the langage RM.

## How to understand with AI?

First, copy/paste in Deepseek (Fast Mode), the code you want to understand, and when Deepseek didn't resolve many times try Claude (Medium Mode). Deepseek didn't resolve the problem sometimes (get up to Expert mode otherwise).

Use more Deepseek because it's unlimited and full power beast. https://chat.deepseek.com/

Claude is token limited and you can't use all the day like Deepseek. https://claude.ai
