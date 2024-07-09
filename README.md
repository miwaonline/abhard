The tool is acting as a proxy betwen in-house accounting application called Abacus and specialised hardware used in retail industry. Its aim is to provide a unified way for Abacus to work with different hardware.

At the moment, there's no well-defined way to run the application, as its still under active development and not enough stable yet to be used outside of developing/testing environment. To run it inside such an environment one should go to the directory with abhard and execute the `run.sh` script.

Abhard is configured through `etc/ahbard.yml` file where different devices can be listed as well as the main port for abhard itself and some other parameters.

Unit testing is done though the standard `unittest` library and thus can be run e.g. like `venv/bin/python3 -m unittest`.