import setuptools

with open("README.md", "r") as fh:
  long_description = fh.read()

with open("requirements.txt", "r") as fh:
  requirements = fh.read()

setuptools.setup(
  name="fim_utils",
  version="0.11",
  author="Ilya Baldin, Hussamudin Nasir",
  description="FABRIC Information Model Library Utilities",
  url="https://github.com/fabric-testbed/information-model-utils",
  long_description="FABRIC Information Model Library Utilities",
  long_description_content_type="text/plain",
  packages=setuptools.find_packages(),
  include_package_data=True,
  classifiers=[
    "Programming Language :: Python :: 3",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
  ],
  python_requires=">=3.9",
  install_requires=requirements,
  setup_requires=requirements,
)
