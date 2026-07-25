function [recovered, extractedEncrypted] = extract_pdfb(stego, cover, options)
%EXTRACT_PDFB Semi-blind coefficient subtraction corresponding to embed_pdfb.

arguments
    stego (:,:) double
    cover (:,:) double
    options.Alpha (1,1) double {mustBePositive} = 0.15
    options.PFilter (1,1) string = "9-7"
    options.DFilter (1,1) string = "pkva"
    options.NLevels (1,:) double = [2 2 2 2]
    options.BandPolicy (1,1) string ...
        {mustBeMember(options.BandPolicy, ["finest","all_details"])} = "finest"
    options.EmbedLowpass (1,1) logical = false
    options.StabilizeHP (1,1) logical = true
end

if ~isequal(size(stego), size(cover))
    error("extract_pdfb:Shape", "Stego and original cover must align.");
end

stegoCoefficients = pdfbdec(stego, char(options.PFilter), ...
    char(options.DFilter), options.NLevels);
coverCoefficients = pdfbdec(cover, char(options.PFilter), ...
    char(options.DFilter), options.NLevels);
extracted = coverCoefficients;
extracted{1} = zeros(size(coverCoefficients{1}), "double");
for level = 2:numel(extracted)
    for direction = 1:numel(extracted{level})
        extracted{level}{direction} = zeros( ...
            size(extracted{level}{direction}), "double");
    end
end

if options.BandPolicy == "finest"
    selectedLevels = numel(extracted);
else
    selectedLevels = 2:numel(extracted);
end
for level = selectedLevels
    for direction = 1:numel(extracted{level})
        extracted{level}{direction} = ( ...
            stegoCoefficients{level}{direction} ...
            - coverCoefficients{level}{direction}) / options.Alpha;
    end
end
if options.EmbedLowpass
    extracted{1} = (stegoCoefficients{1} - coverCoefficients{1}) ...
        / options.Alpha;
end

extractedEncrypted = pdfbrec(extracted, ...
    char(options.PFilter), char(options.DFilter));
recovered = gm_decrypt(extractedEncrypted, options.StabilizeHP);
end

