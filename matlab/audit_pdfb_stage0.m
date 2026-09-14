function report = audit_pdfb_stage0(varargin)
%AUDIT_PDFB_STAGE0 Produce runtime evidence for one explicit PDFB profile.
%
% This function is intentionally audit-only.  It does not enable the
% DIGITAL_A_D embedding path and it never claims that the selected filters
% or directional schedule are the undisclosed settings used by the paper.

parser = inputParser;
addParameter(parser, 'ToolboxPath', '', @(x) ischar(x) || isstring(x));
addParameter(parser, 'OutputPath', '', @(x) ischar(x) || isstring(x));
addParameter(parser, 'Profile', 'matlab_pdfb_explicit_v1', ...
    @(x) ischar(x) || isstring(x));
addParameter(parser, 'AssumptionStatus', 'unverified_interpretation', ...
    @(x) ischar(x) || isstring(x));
addParameter(parser, 'ToolboxRelease', ...
    'Minh Do Contourlet Toolbox 1.0.0.0', ...
    @(x) ischar(x) || isstring(x));
addParameter(parser, 'PFilter', '9-7', @(x) ischar(x) || isstring(x));
addParameter(parser, 'DFilter', 'pkva', @(x) ischar(x) || isstring(x));
addParameter(parser, 'NLevels', [2 2 2 2], ...
    @(x) isnumeric(x) && isvector(x) && ~isempty(x));
addParameter(parser, 'EligiblePyramidLevelFromCoarse', 4, ...
    @(x) isnumeric(x) && isscalar(x) && isfinite(x));
addParameter(parser, 'CoverSize', 512, ...
    @(x) isnumeric(x) && isscalar(x) && isfinite(x));
addParameter(parser, 'RequiredSlots', 222360, ...
    @(x) isnumeric(x) && isscalar(x) && isfinite(x));
addParameter(parser, 'ProbeDelta', 1.0, ...
    @(x) isnumeric(x) && isscalar(x) && isfinite(x) && x > 0);
addParameter(parser, 'ProbeFractions', [0.25 0.5 0.75], ...
    @(x) isnumeric(x) && isvector(x) && ~isempty(x));
addParameter(parser, 'SpecSHA256', '', @(x) ischar(x) || isstring(x));
parse(parser, varargin{:});
options = parser.Results;

toolboxPath = canonical_path(char(options.ToolboxPath));
outputPath = char(options.OutputPath);
assert(isfolder(toolboxPath), 'PDFB:ToolboxMissing', ...
    'Contourlet Toolbox directory does not exist: %s', toolboxPath);
assert(~isempty(outputPath), 'PDFB:OutputMissing', ...
    'OutputPath must be supplied.');
assert(strcmp(char(options.Profile), 'matlab_pdfb_explicit_v1'), ...
    'PDFB:ProfileMismatch', 'Unexpected PDFB profile.');
assert(strcmp(char(options.AssumptionStatus), ...
    'unverified_interpretation'), ...
    'PDFB:ClaimBoundary', ...
    'AssumptionStatus must remain unverified_interpretation.');

addpath(genpath(toolboxPath), '-begin');
pdfbdecPath = which('pdfbdec');
pdfbrecPath = which('pdfbrec');
assert(~isempty(pdfbdecPath), 'PDFB:MissingFunction', ...
    'pdfbdec was not found after adding ToolboxPath.');
assert(~isempty(pdfbrecPath), 'PDFB:MissingFunction', ...
    'pdfbrec was not found after adding ToolboxPath.');
assert(path_is_within(pdfbdecPath, toolboxPath), ...
    'PDFB:PathShadowing', ...
    'Resolved pdfbdec is outside ToolboxPath: %s', pdfbdecPath);
assert(path_is_within(pdfbrecPath, toolboxPath), ...
    'PDFB:PathShadowing', ...
    'Resolved pdfbrec is outside ToolboxPath: %s', pdfbrecPath);

nlevels = double(options.NLevels(:).');
eligibleLevel = double(options.EligiblePyramidLevelFromCoarse);
coverSize = double(options.CoverSize);
requiredSlots = double(options.RequiredSlots);
probeDelta = double(options.ProbeDelta);
probeFractions = double(options.ProbeFractions(:).');
assert(all(nlevels >= 0 & nlevels == floor(nlevels)), ...
    'PDFB:NLevels', 'NLevels must contain non-negative integers.');
assert(eligibleLevel >= 1 && eligibleLevel <= numel(nlevels) && ...
    eligibleLevel == floor(eligibleLevel), ...
    'PDFB:EligibleLevel', ...
    'EligiblePyramidLevelFromCoarse is outside NLevels.');
assert(coverSize == 512, 'PDFB:CoverSize', ...
    'Stage-0 digital audit requires CoverSize=512.');
assert(requiredSlots == 222360, 'PDFB:RequiredSlots', ...
    'Stage-0 digital audit requires RequiredSlots=222360.');
assert(all(probeFractions > 0 & probeFractions < 1), ...
    'PDFB:ProbeFractions', ...
    'ProbeFractions must be strictly inside (0,1).');

[rows, columns] = ndgrid(uint32(0:coverSize - 1), ...
    uint32(0:coverSize - 1));
imageUint8 = uint8(mod( ...
    rows .* uint32(37) + columns .* uint32(19) + ...
    mod(rows .* columns, uint32(251)), ...
    uint32(256)));
image = double(imageUint8);

coefficients = pdfbdec( ...
    image, char(options.PFilter), char(options.DFilter), nlevels);
reconstructed = pdfbrec( ...
    coefficients, char(options.PFilter), char(options.DFilter));
assert(isequal(size(reconstructed), size(image)), ...
    'PDFB:ReconstructionShape', ...
    'pdfbrec output shape differs from the audit input.');
reconstructionDifference = double(reconstructed) - image;

[bands, totalCoefficientCount] = describe_all_bands(coefficients);
eligibleCellIndex = eligibleLevel + 1;
assert(eligibleCellIndex <= numel(coefficients), ...
    'PDFB:CoefficientStructure', ...
    'PDFB output has fewer pyramid levels than requested.');
eligible = coefficients{eligibleCellIndex};
assert(iscell(eligible) && ~isempty(eligible), ...
    'PDFB:EligibleStructure', ...
    'The selected PDFB level is not a non-empty directional cell array.');
[eligibleBands, candidateCoefficientCount] = ...
    describe_directional_bands(eligible, eligibleLevel);

baselineImage = pdfbrec( ...
    coefficients, char(options.PFilter), char(options.DFilter));
baselineRoundTrip = pdfbdec( ...
    baselineImage, char(options.PFilter), char(options.DFilter), nlevels);
baselineEligible = baselineRoundTrip{eligibleCellIndex};
assert(iscell(baselineEligible) && ...
    numel(baselineEligible) == numel(eligible), ...
    'PDFB:RoundTripStructure', ...
    'Re-analysis changed the eligible directional structure.');

probes = struct( ...
    'band_id', {}, ...
    'row', {}, ...
    'column', {}, ...
    'fraction', {}, ...
    'self_gain', {}, ...
    'maximum_cross_talk', {}, ...
    'off_target_l2_ratio', {});
for bandIndex = 1:numel(eligible)
    band = eligible{bandIndex};
    assert(isnumeric(band) && ismatrix(band) && all(isfinite(band(:))), ...
        'PDFB:BandValues', ...
        'Eligible band %d is not a finite numeric matrix.', bandIndex);
    for fractionIndex = 1:numel(probeFractions)
        fraction = probeFractions(fractionIndex);
        row = 1 + floor(fraction * (size(band, 1) - 1));
        column = 1 + floor(fraction * (size(band, 2) - 1));
        modified = coefficients;
        modified{eligibleCellIndex}{bandIndex}(row, column) = ...
            modified{eligibleCellIndex}{bandIndex}(row, column) + probeDelta;
        modifiedImage = pdfbrec( ...
            modified, char(options.PFilter), char(options.DFilter));
        roundTrip = pdfbdec( ...
            modifiedImage, char(options.PFilter), ...
            char(options.DFilter), nlevels);
        roundTripEligible = roundTrip{eligibleCellIndex};
        targetDelta = ...
            double(roundTripEligible{bandIndex}(row, column)) - ...
            double(baselineEligible{bandIndex}(row, column));
        selfGain = targetDelta / probeDelta;
        maximumCrossTalk = 0.0;
        offTargetSquared = 0.0;
        for otherBandIndex = 1:numel(roundTripEligible)
            deltaBand = double(roundTripEligible{otherBandIndex}) - ...
                double(baselineEligible{otherBandIndex});
            if otherBandIndex == bandIndex
                deltaBand(row, column) = 0.0;
            end
            if ~isempty(deltaBand)
                maximumCrossTalk = max( ...
                    maximumCrossTalk, ...
                    max(abs(deltaBand(:))) / abs(probeDelta));
                offTargetSquared = offTargetSquared + ...
                    sum(deltaBand(:) .^ 2);
            end
        end
        probe = struct();
        probe.band_id = sprintf('P%d:D%d', eligibleLevel, bandIndex - 1);
        probe.row = row - 1;
        probe.column = column - 1;
        probe.fraction = fraction;
        probe.self_gain = selfGain;
        probe.maximum_cross_talk = maximumCrossTalk;
        probe.off_target_l2_ratio = ...
            sqrt(offTargetSquared) / abs(probeDelta);
        probes(end + 1) = probe; %#ok<AGROW>
    end
end
assert(~isempty(probes), 'PDFB:NoProbes', ...
    'No independent-writability probes were generated.');

toolbox = struct();
toolbox.declared_release = char(options.ToolboxRelease);
toolbox.root = toolboxPath;
toolbox.pdfbdec_path = canonical_path(pdfbdecPath);
toolbox.pdfbdec_sha256 = sha256_file(pdfbdecPath);
toolbox.pdfbrec_path = canonical_path(pdfbrecPath);
toolbox.pdfbrec_sha256 = sha256_file(pdfbrecPath);
resampcPath = which('resampc');
if isempty(resampcPath)
    toolbox.resampc_path = '';
    toolbox.resampc_sha256 = '';
else
    toolbox.resampc_path = canonical_path(resampcPath);
    toolbox.resampc_sha256 = sha256_file(resampcPath);
end

parameters = struct();
parameters.pfilter = char(options.PFilter);
parameters.dfilter = char(options.DFilter);
parameters.nlevels = nlevels;
parameters.eligible_pyramid_level_from_coarse = eligibleLevel;
parameters.cover_size = coverSize;
parameters.probe_delta = probeDelta;
parameters.probe_fractions = probeFractions;

inputRecord = struct();
inputRecord.generator = 'ctsteg_deterministic_audit_v1';
inputRecord.shape = [coverSize coverSize];
% MATLAB is column-major.  Transposing before linearization hashes the
% canonical row-major uint8 sequence used by the Python validator.
inputRecord.uint8_row_major_sha256 = ...
    sha256_bytes(reshape(imageUint8.', [], 1));

runtime = runtime_record();

perfectReconstruction = struct();
perfectReconstruction.max_abs_error = ...
    max(abs(reconstructionDifference(:)));
perfectReconstruction.mse = ...
    mean(reconstructionDifference(:) .^ 2);
perfectReconstruction.rmse = sqrt(perfectReconstruction.mse);

writability = struct();
writability.coordinate_model = ...
    'raw_pdfb_coefficient_write_then_synthesis_reanalysis';
writability.probe_count = numel(probes);
writability.minimum_self_gain = min([probes.self_gain]);
writability.maximum_cross_talk = max([probes.maximum_cross_talk]);
writability.maximum_off_target_l2_ratio = ...
    max([probes.off_target_l2_ratio]);
writability.probes = probes;

capacity = struct();
capacity.required_slots = requiredSlots;
capacity.candidate_coefficients = candidateCoefficientCount;
capacity.capacity_sufficient = candidateCoefficientCount >= requiredSlots;
capacity.raw_storage_capacity_sufficient = ...
    candidateCoefficientCount >= requiredSlots;
% A Laplacian-pyramid detail image has the same raw sample count as its
% input image, but only N - N/4 independent degrees of freedom because the
% downsampled lowpass carries N/4 degrees.  The critically sampled DFB
% preserves that rank; it does not turn the redundant detail samples into
% independent coordinates.
independentSlotUpperBound = 3 * candidateCoefficientCount / 4;
assert(independentSlotUpperBound == floor(independentSlotUpperBound), ...
    'PDFB:IndependentSlotRank', ...
    'The eligible coefficient count does not yield an integral LP rank.');
capacity.independent_slot_upper_bound = independentSlotUpperBound;
capacity.independent_capacity_sufficient = ...
    independentSlotUpperBound >= requiredSlots;
capacity.unused_candidate_slots = ...
    candidateCoefficientCount - requiredSlots;
capacity.candidate_utilization = ...
    requiredSlots / candidateCoefficientCount;

report = struct();
report.schema = 1;
report.runtime_verified = true;
report.profile = char(options.Profile);
report.spec_sha256 = char(options.SpecSHA256);
report.assumption_status = char(options.AssumptionStatus);
report.author_equivalence_claimed = false;
report.parameters = parameters;
report.input = inputRecord;
report.runtime = runtime;
backend = struct();
backend.label = 'minh_do_contourlet_toolbox_pdfb_v1';
backend.execution_engine = runtime.engine;
backend.resampler = 'resampc_mex';
report.backend = backend;
report.toolbox = toolbox;
report.bands = bands;
report.eligible_bands = eligibleBands;
report.total_coefficients = totalCoefficientCount;
report.redundancy_ratio = totalCoefficientCount / numel(image);
report.capacity = capacity;
report.perfect_reconstruction = perfectReconstruction;
report.independent_writability = writability;
report.paper_difference = [ ...
    'This is one explicit MATLAB PDFB interpretation.  The source paper ' ...
    'does not disclose enough parameters to identify it as the authors'' ' ...
    'configuration.'];

outputDirectory = fileparts(outputPath);
if ~isempty(outputDirectory) && ~isfolder(outputDirectory)
    mkdir(outputDirectory);
end
assert(~isfile(outputPath), 'PDFB:OutputExists', ...
    'Refusing to overwrite existing evidence: %s', outputPath);
encoded = encode_report(report, perfectReconstruction.mse);
fileIdentifier = fopen(outputPath, 'w');
assert(fileIdentifier >= 0, 'PDFB:OutputOpen', ...
    'Could not open evidence output: %s', outputPath);
cleanup = onCleanup(@() fclose(fileIdentifier)); %#ok<NASGU>
fwrite(fileIdentifier, encoded, 'char');
fwrite(fileIdentifier, newline, 'char');
end


function runtime = runtime_record()
runtime = struct();
if exist('OCTAVE_VERSION', 'builtin') ~= 0
    runtime.engine = 'gnu_octave';
    runtime.engine_version = OCTAVE_VERSION;
    runtime.engine_release = 'not_applicable';
    % These legacy schema keys are retained for the existing Python
    % validator.  They must not mislabel an Octave run as MATLAB.
    runtime.matlab_version = 'not_applicable_gnu_octave';
    runtime.matlab_release = 'not_applicable_gnu_octave';
else
    runtime.engine = 'matlab';
    runtime.engine_version = version;
    runtime.engine_release = version('-release');
    runtime.matlab_version = version;
    runtime.matlab_release = version('-release');
end
runtime.computer = computer;
end


function encoded = encode_report(report, reconstructionMse)
encoded = jsonencode(report);
if exist('OCTAVE_VERSION', 'builtin') == 0
    return;
end

% GNU Octave 8.4's jsonencode rounds finite values smaller than roughly
% 1e-15 to JSON zero.  The PDFB round-trip MSE is normally around 1e-22,
% so that behavior makes the serialized MSE disagree with the accurately
% serialized RMSE.  Replace only the named scalar with a round-trip-safe
% scientific representation; all other JSON remains produced by Octave.
mseZero = '"mse":0';
mseValue = ['"mse":' sprintf('%.17g', reconstructionMse)];
occurrences = strfind(encoded, mseZero);
assert(numel(occurrences) == 1, 'PDFB:OctaveJsonMse', ...
    'Expected exactly one rounded reconstruction MSE field.');
encoded = strrep(encoded, mseZero, mseValue);
end


function [records, total] = describe_all_bands(coefficients)
records = struct('band_id', {}, 'shape', {}, 'coefficient_count', {});
total = 0;
assert(iscell(coefficients) && numel(coefficients) >= 2, ...
    'PDFB:CoefficientStructure', ...
    'pdfbdec output must be a cell vector with lowpass and detail levels.');
lowpass = coefficients{1};
records(end + 1) = band_record('P0:LOWPASS', lowpass);
total = total + numel(lowpass);
for cellIndex = 2:numel(coefficients)
    level = cellIndex - 1;
    levelBands = coefficients{cellIndex};
    assert(iscell(levelBands) && ~isempty(levelBands), ...
        'PDFB:CoefficientStructure', ...
        'PDFB detail level %d is not a non-empty cell array.', level);
    for direction = 1:numel(levelBands)
        identifier = sprintf('P%d:D%d', level, direction - 1);
        records(end + 1) = band_record( ...
            identifier, levelBands{direction}); %#ok<AGROW>
        total = total + numel(levelBands{direction});
    end
end
end


function [records, total] = describe_directional_bands(bands, level)
records = struct('band_id', {}, 'shape', {}, 'coefficient_count', {});
total = 0;
for direction = 1:numel(bands)
    identifier = sprintf('P%d:D%d', level, direction - 1);
    records(end + 1) = band_record( ...
        identifier, bands{direction}); %#ok<AGROW>
    total = total + numel(bands{direction});
end
end


function record = band_record(identifier, band)
assert(isnumeric(band) && ismatrix(band) && all(isfinite(band(:))), ...
    'PDFB:BandValues', 'Band %s is not a finite numeric matrix.', identifier);
record = struct();
record.band_id = identifier;
record.shape = [size(band, 1) size(band, 2)];
record.coefficient_count = numel(band);
end


function output = canonical_path(input)
file = javaObject('java.io.File', char(input));
output = char(file.getCanonicalPath());
end


function result = path_is_within(filePath, rootPath)
fileCanonical = canonical_path(filePath);
rootCanonical = canonical_path(rootPath);
rootPrefix = [rootCanonical filesep];
if ispc
    result = startsWith(lower(fileCanonical), lower(rootPrefix));
else
    result = startsWith(fileCanonical, rootPrefix);
end
end


function output = sha256_file(path)
fileIdentifier = fopen(path, 'rb');
assert(fileIdentifier >= 0, 'PDFB:HashOpen', ...
    'Could not open file for hashing: %s', path);
cleanup = onCleanup(@() fclose(fileIdentifier)); %#ok<NASGU>
bytes = fread(fileIdentifier, Inf, '*uint8');
output = sha256_bytes(bytes);
end


function output = sha256_bytes(bytes)
digest = javaMethod( ...
    'getInstance', 'java.security.MessageDigest', 'SHA-256');
digest.update(typecast(uint8(bytes(:)), 'int8'));
hashBytes = typecast(digest.digest(), 'uint8');
output = lower(reshape(dec2hex(hashBytes, 2).', 1, []));
end
