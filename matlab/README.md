# MATLAB PDFB adapter

These files connect the audited AP/GP/HP implementation to Minh N. Do's
Contourlet Toolbox functions `pdfbdec` and `pdfbrec`.

The toolbox is not vendored. Obtain it from the
[MATLAB File Exchange](https://www.mathworks.com/matlabcentral/fileexchange/8837-contourlet-toolbox)
and add it to the MATLAB path.

Example:

```matlab
addpath(genpath("/path/to/contourlet_toolbox"));
addpath("matlab");

summary = run_pair( ...
    "data/usc_sipi/peppers.tiff", ...
    "data/usc_sipi/baboon.tiff", ...
    "results/matlab_literal", ...
    Alpha=0.15, ...
    PFilter="9-7", ...
    DFilter="pkva", ...
    NLevels=[2 2 2 2], ...
    BandPolicy="finest", ...
    EmbedLowpass=false, ...
    QuantizeStego=true);
```

`9-7`, `pkva`, `[2 2 2 2]`, and the selected-band policy are documented
assumptions. The article does not disclose these values. Run a parameter only
because it is methodologically justified, not because it moves a result toward
the published average.

The MATLAB path is supplied for compatibility with the article's stated
platform. It has not been runtime-tested in this repository's Python-only CI,
and must not be described as verified until run with a recorded MATLAB and
Contourlet Toolbox version.

