import setuptools
from fimutil import __VERSION__

with open("README.md", "r") as fh:
  long_description = fh.read()

with open("requirements.txt", "r") as fh:
  requirements = fh.read()

setuptools.setup(
  name="fim_utils",
  version=__VERSION__,
  author="Ilya Baldin, Hussamudin Nasir, Xi Yang",
  description="FABRIC Information Model Library Utilities",
  url="https://github.com/fabric-testbed/information-model-utils",
  long_description="FABRIC Information Model Library Utilities",
  long_description_content_type="text/plain",
  packages=setuptools.find_packages(),
  include_package_data=True,
  scripts=['utilities/scan_worker.py', 'utilities/scan_site.py', 'utilities/scan_net.py'],
  classifiers=[
    "Programming Language :: Python :: 3",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
  ],
  python_requires=">=3.9",
  install_requires=requirements,
  setup_requires=requirements,
)
