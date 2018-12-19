import setuptools

setuptools.setup(
    name='genpersist',
    packages=setuptools.find_packages(),
    tests_require=[
        'pytest',
        'sortedcontainers',
    ],
)

