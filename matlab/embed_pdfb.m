function [stego, encrypted, metadata] = embed_pdfb(cover, secret, options)
%EMBED_PDFB Embed using Minh Do's pdfbdec/pdfbrec Contourlet Toolbox API.
%
% This adapter makes the paper's missing CT choices explicit. It does not
% assert that its defaults equal the undisclosed author configuration.

arguments
    cover (:,:) double
    secret (:,:) double
    options.Alpha (1,1) double {mustBePositive} = 0.15
    options.PFilter (1,1) string = "9-7"
    options.DFilter (1,1) string = "pkva"
    options.NLevels (1,:) double = [2 2 2 2]
    options.BandPolicy (1,1) string ...
        {mustBeMember(options.BandPolicy, ["finest","all_details"])} = "finest"
    options.EmbedLowpass (1,1) logical = false
    options.QuantizeStego (1,1) logical = true
    options.EncryptionMode (1,1) string ...
        {mustBeMember(options.EncryptionMode, ["interpreted","strict"])} = "interpreted"
end

if ~isequal(size(cover), size(secret))
    error("embed_pdfb:Shape", "Cover and secret must have the same shape.");
end
if exist("pdfbdec", "file") ~= 2 || exist("pdfbrec", "file") ~= 2
    error("embed_pdfb:Toolbox", ...
        "pdfbdec/pdfbrec not found. Add the Contourlet Toolbox to path.");
end

encrypted = gm_encrypt(secret, options.EncryptionMode);
coverCoefficients = pdfbdec(cover, char(options.PFilter), ...
    char(options.DFilter), options.NLevels);
secretCoefficients = pdfbdec(encrypted, char(options.PFilter), ...
    char(options.DFilter), options.NLevels);
modified = coverCoefficients;

if options.BandPolicy == "finest"
    selectedLevels = numel(modified);
else
    selectedLevels = 2:numel(modified);
end

for level = selectedLevels
    if ~iscell(modified{level}) || ~iscell(secretCoefficients{level})
        error("embed_pdfb:Structure", "Unexpected PDFB coefficient structure.");
    end
    if numel(modified{level}) ~= numel(secretCoefficients{level})
        error("embed_pdfb:Directions", "Cover/secret direction counts differ.");
    end
    for direction = 1:numel(modified{level})
        if ~isequal(size(modified{level}{direction}), ...
                size(secretCoefficients{level}{direction}))
            error("embed_pdfb:BandShape", "Cover/secret subband sizes differ.");
        end
        modified{level}{direction} = modified{level}{direction} ...
            + options.Alpha * secretCoefficients{level}{direction};
    end
end

if options.EmbedLowpass
    if ~isequal(size(modified{1}), size(secretCoefficients{1}))
        error("embed_pdfb:LowpassShape", "Low-pass sizes differ.");
    end
    modified{1} = modified{1} + options.Alpha * secretCoefficients{1};
end

stego = pdfbrec(modified, char(options.PFilter), char(options.DFilter));
if options.QuantizeStego
    stego = double(uint8(min(max(round(stego), 0), 255)));
end

metadata = struct( ...
    "alpha", options.Alpha, ...
    "pfilter", options.PFilter, ...
    "dfilter", options.DFilter, ...
    "nlevels", options.NLevels, ...
    "band_policy", options.BandPolicy, ...
    "embed_lowpass", options.EmbedLowpass, ...
    "quantize_stego", options.QuantizeStego);
end

