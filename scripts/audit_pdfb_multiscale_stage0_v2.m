function report = audit_pdfb_multiscale_stage0_v2(varargin)
%AUDIT_PDFB_MULTISCALE_STAGE0_V2
% Produce locked Stage-0 evidence for independent P3+P4 PDFB-range
% coordinates under the explicit 9-7/pkva/[2 2 2 2] interpretation.
%
% The coordinate basis is the three critical 9-7 wavelet high-pass arrays
% of each valid Laplacian detail residual at P4 and P3.  Each residual is
% mapped to and from the four raw pkva directional arrays.  This preserves
% the locked PDFB backend while removing the known raw-frame dependency.

parser = inputParser;
addParameter(parser, 'ToolboxPath', '', @(x) ischar(x) || isstring(x));
addParameter(parser, 'OutputPath', '', @(x) ischar(x) || isstring(x));
addParameter(parser, 'ToolboxRelease', ...
    'Minh Do Contourlet Toolbox 1.0.0.0', ...
    @(x) ischar(x) || isstring(x));
addParameter(parser, 'SpecSHA256', '', @(x) ischar(x) || isstring(x));
addParameter(parser, 'ProbeDelta', 1.0, ...
    @(x) isnumeric(x) && isscalar(x) && isfinite(x) && x > 0);
addParameter(parser, 'RequiredSlots', 222360, ...
    @(x) isnumeric(x) && isscalar(x) && isfinite(x));
parse(parser, varargin{:});
options = parser.Results;

toolboxPath = canonical_path(char(options.ToolboxPath));
outputPath = char(options.OutputPath);
probeDelta = double(options.ProbeDelta);
requiredSlots = double(options.RequiredSlots);
assert(isfolder(toolboxPath), 'PDFBRangeV2:ToolboxMissing', ...
    'Contourlet Toolbox directory does not exist: %s', toolboxPath);
assert(~isempty(outputPath), 'PDFBRangeV2:OutputMissing', ...
    'OutputPath must be supplied.');
assert(~isfile(outputPath), 'PDFBRangeV2:OutputExists', ...
    'Refusing to overwrite existing evidence: %s', outputPath);
assert(requiredSlots == 222360, 'PDFBRangeV2:RequiredSlots', ...
    'Stage-0 v2 requires exactly 222360 slots.');

addpath(genpath(toolboxPath), '-begin');
functionNames = { ...
    'pdfbdec', 'pdfbrec', 'pfilters', ...
    'wfb2dec', 'wfb2rec', 'dfbdec_l', 'dfbrec_l'};
functionInventory = function_inventory( ...
    toolboxPath, functionNames);
toolboxInventory = relative_toolbox_inventory( ...
    toolboxPath, functionInventory);
toolboxTreeSHA256 = inventory_tree_sha256(toolboxInventory);
resampcMexPath = canonical_path(fullfile(toolboxPath, 'resampc.mex'));
assert(isfile(resampcMexPath), 'PDFBRangeV2:MissingResampc', ...
    'The locked resampc.mex file is missing: %s', resampcMexPath);
assert(path_is_within(resampcMexPath, toolboxPath), ...
    'PDFBRangeV2:PathShadowing', ...
    'resampc.mex is outside ToolboxPath: %s', resampcMexPath);
resolvedResampcPath = canonical_path(which('resampc'));
assert(strcmp(resolvedResampcPath, resampcMexPath), ...
    'PDFBRangeV2:ResampcResolution', ...
    'Resolved resampc is not the locked resampc.mex: %s', ...
    resolvedResampcPath);
resampcRecord = struct( ...
    'name', 'resampc.mex', ...
    'path', resampcMexPath, ...
    'sha256', sha256_file(resampcMexPath));

scriptPath = canonical_path([mfilename('fullpath') '.m']);
assert(isfile(scriptPath), 'PDFBRangeV2:ScriptIdentity', ...
    'Could not resolve this Stage-0 script.');
scriptSHA256 = sha256_file(scriptPath);
specSHA256 = char(options.SpecSHA256);
if ~isempty(specSHA256)
    assert(numel(specSHA256) == 64 && ...
        all(ismember(lower(specSHA256), '0123456789abcdef')), ...
        'PDFBRangeV2:SpecSHA256', ...
        'SpecSHA256 must be an empty string or 64 hexadecimal characters.');
end

pfilter = '9-7';
dfilter = 'pkva';
nlevels = [2 2 2 2];
[h, g] = pfilters(pfilter);

coverSize = 512;
[rows, columns] = ndgrid(uint32(0:coverSize - 1), ...
    uint32(0:coverSize - 1));
imageUint8 = uint8(mod( ...
    rows .* uint32(37) + columns .* uint32(19) + ...
    mod(rows .* columns, uint32(251)), ...
    uint32(256)));
image = double(imageUint8);

coefficients = pdfbdec(image, pfilter, dfilter, nlevels);
reconstructed = pdfbrec(coefficients, pfilter, dfilter);
assert(isequal(size(reconstructed), size(image)), ...
    'PDFBRangeV2:ReconstructionShape', ...
    'pdfbrec output shape differs from the audit input.');
reconstructionDifference = double(reconstructed) - image;
[rawBands, totalRawCoefficients] = describe_raw_bands(coefficients);

[baselineVirtual, baselineLeakage] = decode_virtual( ...
    coefficients, h, g, dfilter);
virtualBandIds = { ...
    'V:P4:LH', 'V:P4:HL', 'V:P4:HH', ...
    'V:P3:LH', 'V:P3:HL', 'V:P3:HH'};
virtualCounts = cellfun(@numel, baselineVirtual);
assert(isequal(virtualCounts, ...
    [65536 65536 65536 16384 16384 16384]), ...
    'PDFBRangeV2:BandShapes', ...
    'Unexpected multiscale coordinate shapes.');
candidateCoordinates = sum(virtualCounts);
assert(candidateCoordinates == 245760, ...
    'PDFBRangeV2:CoordinateCapacity', ...
    'Expected exactly 245760 independent P3+P4 coordinates.');
assert(candidateCoordinates >= requiredSlots, ...
    'PDFBRangeV2:CoordinateCapacity', ...
    'Independent coordinate pool is smaller than the fixed payload.');

baselineEncoded = encode_virtual( ...
    coefficients, baselineVirtual, h, g, dfilter);
baselineImage = pdfbrec(baselineEncoded, pfilter, dfilter);
baselineRoundTrip = pdfbdec( ...
    baselineImage, pfilter, dfilter, nlevels);
[baselineReadback, baselineReadbackLeakage] = decode_virtual( ...
    baselineRoundTrip, h, g, dfilter);

probeFractions = [0.25 0.5 0.75];
probes = struct( ...
    'band_id', {}, ...
    'row', {}, ...
    'column', {}, ...
    'fraction', {}, ...
    'self_gain', {}, ...
    'maximum_cross_talk', {}, ...
    'off_target_l2_ratio', {});
for bandIndex = 1:numel(baselineVirtual)
    band = baselineVirtual{bandIndex};
    for fractionIndex = 1:numel(probeFractions)
        fraction = probeFractions(fractionIndex);
        row = 1 + floor(fraction * (size(band, 1) - 1));
        column = 1 + floor(fraction * (size(band, 2) - 1));
        modifiedVirtual = copy_cells(baselineVirtual);
        modifiedVirtual{bandIndex}(row, column) = ...
            modifiedVirtual{bandIndex}(row, column) + probeDelta;
        modifiedCoefficients = encode_virtual( ...
            coefficients, modifiedVirtual, h, g, dfilter);
        modifiedImage = pdfbrec( ...
            modifiedCoefficients, pfilter, dfilter);
        roundTrip = pdfbdec( ...
            modifiedImage, pfilter, dfilter, nlevels);
        [readback, ~] = decode_virtual(roundTrip, h, g, dfilter);

        targetDelta = ...
            double(readback{bandIndex}(row, column)) - ...
            double(baselineReadback{bandIndex}(row, column));
        maximumCrossTalk = 0.0;
        offTargetSquared = 0.0;
        for otherBandIndex = 1:numel(readback)
            deltaBand = double(readback{otherBandIndex}) - ...
                double(baselineReadback{otherBandIndex});
            if otherBandIndex == bandIndex
                deltaBand(row, column) = 0.0;
            end
            maximumCrossTalk = max( ...
                maximumCrossTalk, max(abs(deltaBand(:))) / probeDelta);
            offTargetSquared = offTargetSquared + ...
                sum(deltaBand(:) .^ 2);
        end

        probe = struct();
        probe.band_id = virtualBandIds{bandIndex};
        probe.row = row - 1;
        probe.column = column - 1;
        probe.fraction = fraction;
        probe.self_gain = targetDelta / probeDelta;
        probe.maximum_cross_talk = maximumCrossTalk;
        probe.off_target_l2_ratio = sqrt(offTargetSquared) / probeDelta;
        probes(end + 1) = probe; %#ok<AGROW>
    end
end

% Boundary probes are kept separate from the three locked interior probes
% so the original probe-fraction contract remains explicit.
boundaryProbes = struct( ...
    'band_id', {}, ...
    'position', {}, ...
    'row', {}, ...
    'column', {}, ...
    'self_gain', {}, ...
    'maximum_cross_talk', {}, ...
    'off_target_l2_ratio', {});
for bandIndex = 1:numel(baselineVirtual)
    band = baselineVirtual{bandIndex};
    boundaryRows = [1 size(band, 1)];
    boundaryColumns = [1 size(band, 2)];
    boundaryLabels = {'first', 'last'};
    for boundaryIndex = 1:2
        row = boundaryRows(boundaryIndex);
        column = boundaryColumns(boundaryIndex);
        modifiedVirtual = copy_cells(baselineVirtual);
        modifiedVirtual{bandIndex}(row, column) = ...
            modifiedVirtual{bandIndex}(row, column) + probeDelta;
        modifiedCoefficients = encode_virtual( ...
            coefficients, modifiedVirtual, h, g, dfilter);
        modifiedImage = pdfbrec( ...
            modifiedCoefficients, pfilter, dfilter);
        roundTrip = pdfbdec( ...
            modifiedImage, pfilter, dfilter, nlevels);
        [readback, ~] = decode_virtual(roundTrip, h, g, dfilter);

        targetDelta = ...
            double(readback{bandIndex}(row, column)) - ...
            double(baselineReadback{bandIndex}(row, column));
        maximumCrossTalk = 0.0;
        offTargetSquared = 0.0;
        for otherBandIndex = 1:numel(readback)
            deltaBand = double(readback{otherBandIndex}) - ...
                double(baselineReadback{otherBandIndex});
            if otherBandIndex == bandIndex
                deltaBand(row, column) = 0.0;
            end
            maximumCrossTalk = max( ...
                maximumCrossTalk, max(abs(deltaBand(:))) / probeDelta);
            offTargetSquared = offTargetSquared + ...
                sum(deltaBand(:) .^ 2);
        end

        probe = struct();
        probe.band_id = virtualBandIds{bandIndex};
        probe.position = boundaryLabels{boundaryIndex};
        probe.row = row - 1;
        probe.column = column - 1;
        probe.self_gain = targetDelta / probeDelta;
        probe.maximum_cross_talk = maximumCrossTalk;
        probe.off_target_l2_ratio = sqrt(offTargetSquared) / probeDelta;
        boundaryProbes(end + 1) = probe; %#ok<AGROW>
    end
end

% Dense exact-format test:
% P4 uses all 196,608 coordinates.  Each P3 virtual band contributes a
% deterministic 8,584-coordinate prefix, for 222,360 total slots.
denseVirtual = copy_cells(baselineVirtual);
denseMasks = cellfun(@(band) false(size(band)), ...
    baselineVirtual, 'UniformOutput', false);
denseSigns = cellfun(@(band) zeros(size(band)), ...
    baselineVirtual, 'UniformOutput', false);
for bandIndex = 1:3
    denseMasks{bandIndex}(:) = true;
end
for bandIndex = 4:6
    denseMasks{bandIndex}(1:8584) = true;
end
denseSequence = 0;
for bandIndex = 1:numel(denseVirtual)
    selected = find(denseMasks{bandIndex});
    sequence = denseSequence + (1:numel(selected)).';
    pseudoRandom = mod(sequence .* 48271, 2147483647);
    signs = 2.0 * double(pseudoRandom >= 1073741824) - 1.0;
    denseSigns{bandIndex}(selected) = signs;
    denseVirtual{bandIndex}(selected) = ...
        denseVirtual{bandIndex}(selected) + probeDelta * signs;
    denseSequence = denseSequence + numel(selected);
end
assert(denseSequence == requiredSlots, 'PDFBRangeV2:DenseSlotCount', ...
    'Dense trial does not contain exactly 222360 selected coordinates.');
denseCoefficients = encode_virtual( ...
    coefficients, denseVirtual, h, g, dfilter);
denseImage = pdfbrec(denseCoefficients, pfilter, dfilter);
denseRoundTrip = pdfbdec(denseImage, pfilter, dfilter, nlevels);
[denseReadback, denseReadbackLeakage] = decode_virtual( ...
    denseRoundTrip, h, g, dfilter);
denseMaximumAbsoluteError = 0.0;
denseSquaredError = 0.0;
denseSignErrors = 0;
denseOffTargetSquared = 0.0;
for bandIndex = 1:numel(denseReadback)
    deltaBand = double(denseReadback{bandIndex}) - ...
        double(baselineReadback{bandIndex});
    targetBand = probeDelta * denseSigns{bandIndex};
    selected = denseMasks{bandIndex};
    errors = deltaBand(selected) - targetBand(selected);
    denseMaximumAbsoluteError = max( ...
        denseMaximumAbsoluteError, max(abs(errors(:))));
    denseSquaredError = denseSquaredError + sum(errors(:) .^ 2);
    denseSignErrors = denseSignErrors + sum( ...
        sign_with_positive_zero(deltaBand(selected)) ~= ...
        sign_with_positive_zero(targetBand(selected)));
    unselected = ~selected;
    denseOffTargetSquared = denseOffTargetSquared + ...
        sum(deltaBand(unselected) .^ 2);
end

% Full-candidate dense test over all 245,760 independent coordinates.
fullDenseVirtual = copy_cells(baselineVirtual);
fullDenseSigns = cellfun(@(band) zeros(size(band)), ...
    baselineVirtual, 'UniformOutput', false);
fullDenseSequence = 0;
for bandIndex = 1:numel(fullDenseVirtual)
    count = numel(fullDenseVirtual{bandIndex});
    sequence = fullDenseSequence + (1:count).';
    pseudoRandom = mod((sequence + 20260730) .* 48271, 2147483647);
    signs = 2.0 * double(pseudoRandom >= 1073741824) - 1.0;
    fullDenseSigns{bandIndex}(:) = signs;
    fullDenseVirtual{bandIndex}(:) = ...
        fullDenseVirtual{bandIndex}(:) + probeDelta * signs;
    fullDenseSequence = fullDenseSequence + count;
end
assert(fullDenseSequence == candidateCoordinates, ...
    'PDFBRangeV2:FullDenseSlotCount', ...
    'Full dense trial does not cover the complete coordinate pool.');
fullDenseCoefficients = encode_virtual( ...
    coefficients, fullDenseVirtual, h, g, dfilter);
fullDenseImage = pdfbrec(fullDenseCoefficients, pfilter, dfilter);
fullDenseRoundTrip = pdfbdec( ...
    fullDenseImage, pfilter, dfilter, nlevels);
[fullDenseReadback, fullDenseReadbackLeakage] = decode_virtual( ...
    fullDenseRoundTrip, h, g, dfilter);
fullDenseMaximumAbsoluteError = 0.0;
fullDenseSquaredError = 0.0;
fullDenseSignErrors = 0;
for bandIndex = 1:numel(fullDenseReadback)
    deltaBand = double(fullDenseReadback{bandIndex}) - ...
        double(baselineReadback{bandIndex});
    targetBand = probeDelta * fullDenseSigns{bandIndex};
    errors = deltaBand - targetBand;
    fullDenseMaximumAbsoluteError = max( ...
        fullDenseMaximumAbsoluteError, max(abs(errors(:))));
    fullDenseSquaredError = ...
        fullDenseSquaredError + sum(errors(:) .^ 2);
    fullDenseSignErrors = fullDenseSignErrors + sum( ...
        sign_with_positive_zero(deltaBand(:)) ~= ...
        sign_with_positive_zero(targetBand(:)));
end

minimumSelfGain = min([probes.self_gain]);
maximumCrossTalk = max([probes.maximum_cross_talk]);
maximumOffTargetL2Ratio = max([probes.off_target_l2_ratio]);
boundaryMinimumSelfGain = min([boundaryProbes.self_gain]);
boundaryMaximumCrossTalk = ...
    max([boundaryProbes.maximum_cross_talk]);
boundaryMaximumOffTargetL2Ratio = ...
    max([boundaryProbes.off_target_l2_ratio]);
reconstructionMaxAbs = max(abs(reconstructionDifference(:)));
probesPerBand = numel(probeFractions);
maximumRangeLeakage = max([ ...
    baselineLeakage baselineReadbackLeakage ...
    denseReadbackLeakage fullDenseReadbackLeakage]);

thresholds = struct( ...
    'reconstruction_max_abs', 1e-8, ...
    'minimum_self_gain', 0.99, ...
    'maximum_cross_talk', 0.01, ...
    'maximum_off_target_l2_ratio', 0.05, ...
    'valid_range_lowpass_max_abs', 1e-8, ...
    'dense_maximum_absolute_coordinate_error', 1e-8, ...
    'dense_relative_l2_error', 1e-10, ...
    'minimum_probes_per_band', 3, ...
    'required_slots', requiredSlots);
gate = struct();
gate.reconstruction_passed = ...
    reconstructionMaxAbs <= thresholds.reconstruction_max_abs;
gate.capacity_passed = candidateCoordinates >= requiredSlots;
gate.rank_passed = candidateCoordinates >= requiredSlots;
gate.probe_coverage_passed = probesPerBand >= ...
    thresholds.minimum_probes_per_band;
gate.self_gain_passed = ...
    minimumSelfGain >= thresholds.minimum_self_gain;
gate.cross_talk_passed = ...
    maximumCrossTalk <= thresholds.maximum_cross_talk;
gate.off_target_passed = ...
    maximumOffTargetL2Ratio <= thresholds.maximum_off_target_l2_ratio;
gate.boundary_probes_passed = ...
    boundaryMinimumSelfGain >= thresholds.minimum_self_gain && ...
    boundaryMaximumCrossTalk <= thresholds.maximum_cross_talk && ...
    boundaryMaximumOffTargetL2Ratio <= ...
        thresholds.maximum_off_target_l2_ratio;
gate.valid_range_leakage_passed = ...
    maximumRangeLeakage <= thresholds.valid_range_lowpass_max_abs;
gate.dense_sign_trial_passed = denseSignErrors == 0;
gate.full_candidate_dense_trial_passed = ...
    fullDenseSignErrors == 0 && ...
    fullDenseMaximumAbsoluteError <= ...
        thresholds.dense_maximum_absolute_coordinate_error && ...
    sqrt(fullDenseSquaredError) / ...
        (probeDelta * sqrt(candidateCoordinates)) <= ...
        thresholds.dense_relative_l2_error;
gate.passed = ...
    gate.reconstruction_passed && ...
    gate.capacity_passed && ...
    gate.rank_passed && ...
    gate.probe_coverage_passed && ...
    gate.self_gain_passed && ...
    gate.cross_talk_passed && ...
    gate.off_target_passed && ...
    gate.boundary_probes_passed && ...
    gate.valid_range_leakage_passed && ...
    gate.dense_sign_trial_passed && ...
    gate.full_candidate_dense_trial_passed;

runtime = runtime_record();
toolbox = struct();
toolbox.declared_release = char(options.ToolboxRelease);
toolbox.root = toolboxPath;
toolbox.function_inventory = functionInventory;
toolbox.inventory = toolboxInventory;
toolbox.inventory_policy = 'all_regular_files_recursive_v1';
toolbox.inventory_count = numel(toolboxInventory);
toolbox.tree_sha256 = toolboxTreeSHA256;
toolbox.resampc_mex = resampcRecord;
toolbox.resampc_resolved_path = resolvedResampcPath;
toolbox.pdfbdec_path = inventory_value( ...
    functionInventory, 'pdfbdec', 'path');
toolbox.pdfbdec_sha256 = inventory_value( ...
    functionInventory, 'pdfbdec', 'sha256');
toolbox.pdfbrec_path = inventory_value( ...
    functionInventory, 'pdfbrec', 'path');
toolbox.pdfbrec_sha256 = inventory_value( ...
    functionInventory, 'pdfbrec', 'sha256');

source = struct();
source.script_path = scriptPath;
source.script_sha256 = scriptSHA256;
source.spec_sha256 = specSHA256;

parameters = struct();
parameters.pfilter = pfilter;
parameters.dfilter = dfilter;
parameters.nlevels = nlevels;
parameters.eligible_pyramid_levels_from_coarse = [3 4];
parameters.cover_size = coverSize;
parameters.required_slots = requiredSlots;
parameters.probe_delta = probeDelta;
parameters.probe_fractions = probeFractions;
parameters.coordinate_order = virtualBandIds;

inputRecord = struct();
inputRecord.generator = 'ctsteg_deterministic_audit_v1';
inputRecord.shape = [coverSize coverSize];
inputRecord.uint8_row_major_sha256 = ...
    sha256_bytes(reshape(imageUint8.', [], 1));

capacity = struct();
capacity.required_slots = requiredSlots;
capacity.candidate_coefficients = candidateCoordinates;
capacity.candidate_coordinates = candidateCoordinates;
capacity.coordinate_basis_rank = candidateCoordinates;
capacity.capacity_sufficient = candidateCoordinates >= requiredSlots;
capacity.unused_candidate_slots = candidateCoordinates - requiredSlots;
capacity.candidate_utilization = requiredSlots / candidateCoordinates;

rankCertificate = struct();
rankCertificate.p4_raw_directional_values = 262144;
rankCertificate.p4_independent_coordinates = 196608;
rankCertificate.p3_raw_directional_values = 65536;
rankCertificate.p3_independent_coordinates = 49152;
rankCertificate.p3_p4_independent_coordinates = candidateCoordinates;
rankCertificate.formula = ...
    'rank(I-GH)=3N/4 per level because HG=I';
rankCertificate.construction = ...
    'three critical 9-7 highpass coordinates per 2x2 block per level';

perfectReconstruction = struct();
perfectReconstruction.max_abs_error = reconstructionMaxAbs;
perfectReconstruction.rmse = ...
    sqrt(mean(reconstructionDifference(:) .^ 2));

rangeLeakage = struct();
rangeLeakage.baseline_p4_lowpass_max_abs = baselineLeakage(1);
rangeLeakage.baseline_p3_lowpass_max_abs = baselineLeakage(2);
rangeLeakage.baseline_readback_p4_lowpass_max_abs = ...
    baselineReadbackLeakage(1);
rangeLeakage.baseline_readback_p3_lowpass_max_abs = ...
    baselineReadbackLeakage(2);
rangeLeakage.dense_readback_p4_lowpass_max_abs = ...
    denseReadbackLeakage(1);
rangeLeakage.dense_readback_p3_lowpass_max_abs = ...
    denseReadbackLeakage(2);
rangeLeakage.full_dense_readback_p4_lowpass_max_abs = ...
    fullDenseReadbackLeakage(1);
rangeLeakage.full_dense_readback_p3_lowpass_max_abs = ...
    fullDenseReadbackLeakage(2);
rangeLeakage.maximum_observed = maximumRangeLeakage;
rangeLeakage.threshold = thresholds.valid_range_lowpass_max_abs;
rangeLeakage.gate_passed = gate.valid_range_leakage_passed;

writability = struct();
writability.coordinate_semantics = [ ...
    'decoded independent multiscale PDFB-range coordinates after locked ' ...
    'PDFB synthesize/reanalyze'];
writability.probe_count = numel(probes);
writability.probes_per_band = probesPerBand;
writability.minimum_self_gain = minimumSelfGain;
writability.maximum_cross_talk = maximumCrossTalk;
writability.maximum_off_target_l2_ratio = maximumOffTargetL2Ratio;
writability.probes = probes;

boundaryWritability = struct();
boundaryWritability.probe_count = numel(boundaryProbes);
boundaryWritability.positions_per_band = 2;
boundaryWritability.minimum_self_gain = boundaryMinimumSelfGain;
boundaryWritability.maximum_cross_talk = boundaryMaximumCrossTalk;
boundaryWritability.maximum_off_target_l2_ratio = ...
    boundaryMaximumOffTargetL2Ratio;
boundaryWritability.gate_passed = gate.boundary_probes_passed;
boundaryWritability.probes = boundaryProbes;

denseTrial = struct();
denseTrial.slot_count = denseSequence;
denseTrial.selection = ...
    'all P4 coordinates plus first 8584 coordinates of each P3 band';
denseTrial.sign_generator = ...
    'park_miller_48271_thresholded_v1';
denseTrial.sign_errors = denseSignErrors;
denseTrial.maximum_absolute_coordinate_error = ...
    denseMaximumAbsoluteError;
denseTrial.selected_l2_error_ratio = ...
    sqrt(denseSquaredError) / (probeDelta * sqrt(requiredSlots));
denseTrial.unselected_l2_ratio = ...
    sqrt(denseOffTargetSquared) / (probeDelta * sqrt(requiredSlots));

fullDenseTrial = struct();
fullDenseTrial.slot_count = fullDenseSequence;
fullDenseTrial.selection = 'all independent P3+P4 coordinates';
fullDenseTrial.sign_generator = ...
    'park_miller_48271_thresholded_offset_20260730_v1';
fullDenseTrial.sign_errors = fullDenseSignErrors;
fullDenseTrial.maximum_absolute_coordinate_error = ...
    fullDenseMaximumAbsoluteError;
fullDenseTrial.selected_l2_error_ratio = ...
    sqrt(fullDenseSquaredError) / ...
    (probeDelta * sqrt(candidateCoordinates));
fullDenseTrial.maximum_valid_range_lowpass_abs = ...
    max(fullDenseReadbackLeakage);
fullDenseTrial.gate_passed = ...
    gate.full_candidate_dense_trial_passed;

report = struct();
report.schema = 2;
report.runtime_verified = true;
report.profile = 'octave_pdfb_range_coordinates_v2';
report.scheme = ...
    'pdfb_9_7_pkva_multiscale_range_coordinates_p3_p4_v2';
report.exploratory = false;
report.assumption_status = 'unverified_interpretation';
report.author_equivalence_claimed = false;
report.claim_boundary = [ ...
    'Independent multiscale coordinates in the P3+P4 range of the locked ' ...
    '9-7/pkva PDFB; not raw directional-array coefficients and not ' ...
    'author-equivalent settings.'];
report.runtime = runtime;
report.backend = struct( ...
    'label', 'minh_do_contourlet_toolbox_pdfb_range_coordinates_v2', ...
    'execution_engine', runtime.engine, ...
    'resampler', 'resampc.mex');
report.toolbox = toolbox;
report.toolbox_inventory = toolboxInventory;
report.toolbox_inventory_policy = ...
    'all_regular_files_recursive_v1';
report.toolbox_inventory_count = numel(toolboxInventory);
report.toolbox_tree_sha256 = toolboxTreeSHA256;
report.source = source;
report.parameters = parameters;
report.input = inputRecord;
report.raw_bands = rawBands;
report.total_raw_coefficients = totalRawCoefficients;
report.raw_redundancy_ratio = ...
    totalRawCoefficients / numel(image);
report.virtual_bands = band_records(virtualBandIds, baselineVirtual);
report.capacity = capacity;
report.rank_certificate = rankCertificate;
report.perfect_reconstruction = perfectReconstruction;
report.valid_range_leakage = rangeLeakage;
report.independent_writability = writability;
report.boundary_writability = boundaryWritability;
report.dense_222360_sign_trial = denseTrial;
report.dense_245760_full_candidate_trial = fullDenseTrial;
report.locked_thresholds = thresholds;
report.gate = gate;
report.passed = gate.passed;

outputDirectory = fileparts(outputPath);
if ~isempty(outputDirectory) && ~isfolder(outputDirectory)
    mkdir(outputDirectory);
end
fileIdentifier = fopen(outputPath, 'w');
assert(fileIdentifier >= 0, 'PDFBRangeV2:OutputOpen', ...
    'Could not open evidence output: %s', outputPath);
cleanup = onCleanup(@() fclose(fileIdentifier)); %#ok<NASGU>
fwrite(fileIdentifier, jsonencode(report), 'char');
fwrite(fileIdentifier, newline, 'char');

fprintf( ...
    ['schema=%d profile=%s capacity=%d required=%d self=%.17g ' ...
     'cross=%.17g off_l2=%.17g dense_sign_errors=%d ' ...
     'full_dense_sign_errors=%d boundary_self=%.17g ' ...
     'range_leakage=%.17g reconstruction=%.17g passed=%d\n'], ...
    report.schema, report.profile, candidateCoordinates, requiredSlots, ...
    minimumSelfGain, maximumCrossTalk, maximumOffTargetL2Ratio, ...
    denseSignErrors, fullDenseSignErrors, boundaryMinimumSelfGain, ...
    maximumRangeLeakage, reconstructionMaxAbs, report.passed);
end


function [virtual, leakage] = decode_virtual(coefficients, h, g, dfilter)
assert(iscell(coefficients) && numel(coefficients) == 5, ...
    'PDFBRangeV2:CoefficientStructure', ...
    'Expected the locked five-cell PDFB structure.');
detailP4 = dfbrec_l(coefficients{5}, dfilter);
[lowP4, p4LH, p4HL, p4HH] = wfb2dec(detailP4, h, g);
detailP3 = dfbrec_l(coefficients{4}, dfilter);
[lowP3, p3LH, p3HL, p3HH] = wfb2dec(detailP3, h, g);
virtual = {p4LH, p4HL, p4HH, p3LH, p3HL, p3HH};
leakage = [max(abs(lowP4(:))) max(abs(lowP3(:)))];
end


function output = encode_virtual( ...
        baselineCoefficients, virtual, h, g, dfilter)
assert(numel(virtual) == 6, 'PDFBRangeV2:BandCount', ...
    'Expected six virtual bands.');
output = baselineCoefficients;
detailP4 = wfb2rec( ...
    zeros(size(virtual{1})), ...
    virtual{1}, virtual{2}, virtual{3}, h, g);
detailP3 = wfb2rec( ...
    zeros(size(virtual{4})), ...
    virtual{4}, virtual{5}, virtual{6}, h, g);
output{5} = dfbdec_l(detailP4, dfilter, 2);
output{4} = dfbdec_l(detailP3, dfilter, 2);
end


function output = copy_cells(input)
output = cell(size(input));
for index = 1:numel(input)
    output{index} = input{index};
end
end


function output = sign_with_positive_zero(input)
output = ones(size(input));
output(input < 0) = -1;
end


function records = band_records(identifiers, bands)
records = struct( ...
    'band_id', {}, 'shape', {}, 'coordinate_count', {});
for index = 1:numel(bands)
    record = struct();
    record.band_id = identifiers{index};
    record.shape = [size(bands{index}, 1) size(bands{index}, 2)];
    record.coordinate_count = numel(bands{index});
    records(end + 1) = record; %#ok<AGROW>
end
end


function [records, total] = describe_raw_bands(coefficients)
records = struct( ...
    'band_id', {}, 'shape', {}, 'coefficient_count', {});
total = 0;
lowpass = coefficients{1};
records(end + 1) = raw_band_record('P0:LOWPASS', lowpass);
total = total + numel(lowpass);
for cellIndex = 2:numel(coefficients)
    level = cellIndex - 1;
    for direction = 1:numel(coefficients{cellIndex})
        identifier = sprintf('P%d:D%d', level, direction - 1);
        band = coefficients{cellIndex}{direction};
        records(end + 1) = raw_band_record( ...
            identifier, band); %#ok<AGROW>
        total = total + numel(band);
    end
end
end


function record = raw_band_record(identifier, band)
assert(isnumeric(band) && ismatrix(band) && all(isfinite(band(:))), ...
    'PDFBRangeV2:RawBand', 'Raw band %s is invalid.', identifier);
record = struct();
record.band_id = identifier;
record.shape = [size(band, 1) size(band, 2)];
record.coefficient_count = numel(band);
end


function records = function_inventory(toolboxPath, names)
records = struct('name', {}, 'path', {}, 'sha256', {});
for index = 1:numel(names)
    name = names{index};
    resolved = which(name);
    assert(~isempty(resolved), 'PDFBRangeV2:MissingFunction', ...
        'Required function was not found: %s', name);
    resolved = canonical_path(resolved);
    assert(path_is_within(resolved, toolboxPath), ...
        'PDFBRangeV2:PathShadowing', ...
        'Resolved %s is outside ToolboxPath: %s', name, resolved);
    record = struct();
    record.name = name;
    record.path = resolved;
    record.sha256 = sha256_file(resolved);
    records(end + 1) = record; %#ok<AGROW>
end
end


function records = relative_toolbox_inventory(toolboxPath, functionRecords)
paths = regular_files_recursive(toolboxPath);
paths = unique(paths);
relativePaths = cell(size(paths));
rootPrefix = [canonical_path(toolboxPath) filesep];
for index = 1:numel(paths)
    assert(path_is_within(paths{index}, toolboxPath), ...
        'PDFBRangeV2:InventoryPath', ...
        'Toolbox inventory path is outside ToolboxPath: %s', paths{index});
    relativePaths{index} = strrep( ...
        paths{index}(numel(rootPrefix) + 1:end), filesep, '/');
end
[relativePaths, order] = sort(relativePaths);
paths = paths(order);
records = struct('path', {}, 'sha256', {});
for index = 1:numel(paths)
    record = struct();
    record.path = relativePaths{index};
    record.sha256 = sha256_file(paths{index});
    records(end + 1) = record; %#ok<AGROW>
end
requiredRelative = { ...
    'pdfbdec.m', 'pdfbrec.m', 'pfilters.m', ...
    'wfb2dec.m', 'wfb2rec.m', 'dfbdec_l.m', 'dfbrec_l.m'};
assert(all(ismember(requiredRelative, {records.path})), ...
    'PDFBRangeV2:InventoryRequired', ...
    'Toolbox inventory is missing a required MATLAB source.');
assert(any(strcmp({records.path}, 'resampc.mex')), ...
    'PDFBRangeV2:InventoryRequired', ...
    'Toolbox inventory is missing resampc.mex.');
resolvedRequired = {functionRecords.path};
assert(all(ismember(resolvedRequired, paths)), ...
    'PDFBRangeV2:InventoryRequired', ...
    'Toolbox inventory does not close over all resolved functions.');
end


function paths = regular_files_recursive(root)
paths = {};
entries = dir(root);
for index = 1:numel(entries)
    name = entries(index).name;
    if strcmp(name, '.') || strcmp(name, '..')
        continue;
    end
    path = fullfile(root, name);
    if entries(index).isdir
        nested = regular_files_recursive(path);
        paths = [paths nested]; %#ok<AGROW>
    else
        paths{end + 1} = canonical_path(path); %#ok<AGROW>
    end
end
end


function output = inventory_tree_sha256(records)
serialized = uint8([]);
for index = 1:numel(records)
    line = [records(index).path char(0) ...
        records(index).sha256 newline];
    serialized = [serialized uint8(line)]; %#ok<AGROW>
end
output = sha256_bytes(serialized);
end


function output = inventory_value(records, name, field)
matches = find(strcmp({records.name}, name));
assert(numel(matches) == 1, 'PDFBRangeV2:InventoryLookup', ...
    'Inventory lookup for %s was not unique.', name);
output = records(matches).(field);
end


function runtime = runtime_record()
runtime = struct();
if exist('OCTAVE_VERSION', 'builtin') ~= 0
    runtime.engine = 'gnu_octave';
    runtime.version = OCTAVE_VERSION;
    runtime.platform = computer;
    runtime.executable = canonical_path('/proc/self/exe');
    runtime.engine_version = OCTAVE_VERSION;
    runtime.engine_release = 'not_applicable';
    runtime.matlab_version = 'not_applicable_gnu_octave';
    runtime.matlab_release = 'not_applicable_gnu_octave';
    runtime.utc_timestamp = ...
        strftime('%Y-%m-%dT%H:%M:%SZ', gmtime(time()));
else
    runtime.engine = 'matlab';
    runtime.version = version;
    runtime.platform = computer;
    runtime.executable = canonical_path('/proc/self/exe');
    runtime.engine_version = version;
    runtime.engine_release = version('-release');
    runtime.matlab_version = version;
    runtime.matlab_release = version('-release');
    runtime.utc_timestamp = ...
        char(datetime('now', 'TimeZone', 'UTC', ...
        'Format', 'yyyy-MM-dd''T''HH:mm:ss''Z'''));
end
runtime.computer = computer;
end


function output = canonical_path(input)
if exist('OCTAVE_VERSION', 'builtin') ~= 0
    output = canonicalize_file_name(char(input));
    if isempty(output)
        output = char(input);
    end
else
    file = javaObject('java.io.File', char(input));
    output = char(file.getCanonicalPath());
end
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
assert(fileIdentifier >= 0, 'PDFBRangeV2:HashOpen', ...
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
