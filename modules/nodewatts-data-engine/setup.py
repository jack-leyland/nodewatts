from setuptools import setup, find_packages

    
setup(
    # Basic info
    name='nwengine',
    version='0.0.1',
    author='Jack Leyland',
    author_email='jackjleyland@gmail.com',
    url='https://github.com/jack-leyland/nodewatts-engine',
    description='Data processing engine used by NodeWatts',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: MIT',
        'Operating System :: POSIX',
        'Programming Language :: Python',
    ],

    # Packages and depencies
    packages=find_packages(),
    python_requires='~=3.10',
    install_requires=[
        "networkx~=2.8.4",
        "pymongo~=4.1.1",
    ],
    zip_safe = False
)