This repository contains the source code of `abhard` project. Please keep in mind you cannot run `abhard` without additional encryption libraries that are not included into the repo. You can find libraries for Linux [here](https://acsk.privatbank.ua/arch/iitlib/EUSignCP-Linux-Python-20200730.zip) and for Windows [here](https://acsk.privatbank.ua/arch/iitlib/EUSignCP-MSWindows-Python-20200730.zip). Both archives include x32 and x64 flavours for various python versions.


To get the thing up and running on a system with newer (3.10+) versions of Python:

```bash
docker build --tag abhard .
docker run --publish 8080:8080 abhard
```
