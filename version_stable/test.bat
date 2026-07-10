del RmLang*.py RmLang*.tokens RmLang*.interp
java -jar antlr-4.13.1-complete.jar -visitor -no-listener RmLang.g4

ipython3 test_rm.py exemple.rm