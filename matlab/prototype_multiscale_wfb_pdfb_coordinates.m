function report = prototype_multiscale_wfb_pdfb_coordinates(varargin)
%PROTOTYPE_MULTISCALE_WFB_PDFB_COORDINATES Constructively audit P3+P4.
%
% Minh Do's Laplacian-pyramid detail at each scale has only three quarters
% of the apparent raw directional-coefficient rank.  The matching 9-7
% wavelet filter bank supplies a constructive coordinate chart for exactly
% that nullspace: (LH, HL, HH) -> wfb2rec(0, LH, HL, HH).  The resulting
% detail has zero LP lowpass, and pkva DFB analysis maps it into the actual
% PDFB directional representation.
%
% This prototype deliberately creates a new coordinate model.  It does not
% claim that raw PDFB directional coefficients are independently writable.

parser = inputParser;
addParameter(parser, 'ToolboxPath', '', @(x) ischar(x) || isstring(x));
addParameter(parser, 'OutputPath', '', @(x) ischar(x) || isstring(x));
addParameter(parser, 'PFilter', '9-7', @(x) ischar(x) || isstring(x));
addParameter(parser, 'DFilter', 'pkva', @(x) ischar(x) || isstring(x));
addParameter(parser, 'NLevels', [2 2 2 2], ...
    @(x) isnumeric(x) && isvector(x) && numel(x) == 4);
addParameter(parser, 'CoverSize', 512, ...
    @(x) isnumeric(x) && isscalar(x) && x == 512);
addParameter(parser, 'RequiredSlots', 222360, ...
    @(x) isnumeric(x) && isscalar(x) && x == 222360);
addParameter(parser, 'ProbeDelta', 1.0, ...
    @(x) isnumeric(x) && isscalar(x) && isfinite(x) && x > 0);
parse(parser, varargin{:});
options = parser.Results;

toolboxPath = canonical_path(char(options.ToolboxPath));
assert(isfolder(toolboxPath), sprintf( ...
    'Toolbox directory does not exist: %s', toolboxPath));
addpath(genpath(toolboxPath), '-begin');

pfilter = char(options.PFilter);
dfilter = char(options.DFilter);
nlevels = double(options.NLevels(:).');
coverSize = double(options.CoverSize);
requiredSlots = double(options.RequiredSlots);
probeDelta = double(options.ProbeDelta);
assert(strcmp(pfilter, '9-7'), ...
    'This coordinate construction is locked to pfilter 9-7.');
assert(strcmp(dfilter, 'pkva'), ...
    'This coordinate construction is locked to dfilter pkva.');
assert(isequal(nlevels, [2 2 2 2]), ...
    'This coordinate construction is locked to [2 2 2 2].');

requiredFunctions = { ...
    'pdfbdec', 'pdfbrec', 'dfbdec_l', 'dfbrec_l', ...
    'wfb2dec', 'wfb2rec', 'lpdec', 'lprec', 'pfilters'};
functionInventory = struct( ...
    'name', {}, 'path', {}, 'sha256', {});
for index = 1:numel(requiredFunctions)
    name = requiredFunctions{index};
    resolved = which(name);
    assert(~isempty(resolved), sprintf( ...
        'Required function was not resolved: %s', name));
    resolved = canonical_path(resolved);
    assert(path_is_within(resolved, toolboxPath), sprintf( ...
        'Resolved %s outside the locked toolbox: %s', name, resolved));
    item = struct();
    item.name = name;
    item.path = resolved;
    item.sha256 = sha256_file(resolved);
    functionInventory(end + 1) = item; %#ok<AGROW>
end

[h, g] = pfilters(pfilter);
template = pdfbdec(zeros(coverSize, coverSize), ...
    pfilter, dfilter, nlevels);
assert(numel(template) == 5, ...
    'Expected lowpass plus four PDFB detail levels.');

coordinateShapes = { ...
    [256 256], [256 256], [256 256], ...
    [128 128], [128 128], [128 128]};
coordinateIds = { ...
    'P4:W-LH', 'P4:W-HL', 'P4:W-HH', ...
    'P3:W-LH', 'P3:W-HL', 'P3:W-HH'};
coordinateCounts = cellfun(@prod, coordinateShapes);
candidateSlots = sum(coordinateCounts);
assert(candidateSlots == 245760, ...
    'P3+P4 constructive coordinate capacity changed unexpectedly.');
assert(requiredSlots <= candidateSlots, ...
    'Required payload exceeds constructive coordinate capacity.');

% First validate lossless conversion of a real analyzed image into this
% coordinate chart and back through actual pkva/PDFB coefficient cells.
[rows, columns] = ndgrid(uint32(0:coverSize - 1), ...
    uint32(0:coverSize - 1));
image = double(uint8(mod( ...
    rows .* uint32(37) + columns .* uint32(19) + ...
    mod(rows .* columns, uint32(251)), uint32(256))));
raw = pdfbdec(image, pfilter, dfilter, nlevels);
rawReconstruction = pdfbrec(raw, pfilter, dfilter);
rawReconstructionError = double(rawReconstruction) - image;

[coverCoordinates, coverNullLowpass, coverDfbRoundtrip] = ...
    raw_to_coordinates(raw, h, g, dfilter);
coverCoordinateNorm = coordinate_norm(coverCoordinates);
coordinateRaw = coordinates_to_raw( ...
    coverCoordinates, raw, h, g, dfilter);
coordinateReconstruction = pdfbrec( ...
    coordinateRaw, pfilter, dfilter);
coordinateReconstructionError = ...
    double(coordinateReconstruction) - image;

% A dense simultaneous Rademacher write is much stronger than isolated
% probes for detecting hidden coupling across the complete 245760-D chart.
set_reproducible_seed(20260730);
denseTarget = zero_coordinates(coordinateShapes);
for index = 1:numel(denseTarget)
    denseTarget{index} = ...
        2.0 .* double(rand(coordinateShapes{index}) >= 0.5) - 1.0;
end
denseRaw = coordinates_to_raw( ...
    denseTarget, zero_raw_like(template), h, g, dfilter);
denseImage = pdfbrec(denseRaw, pfilter, dfilter);
denseAnalyzed = pdfbdec(denseImage, pfilter, dfilter, nlevels);
[denseObserved, denseNullLowpass, denseDfbRoundtrip] = ...
    raw_to_coordinates(denseAnalyzed, h, g, dfilter);
[denseMaximumAbsoluteError, denseRelativeL2Error] = ...
    coordinate_error(denseObserved, denseTarget);
denseTargetNorm = coordinate_norm(denseTarget);
denseCoarseLeakage = ...
    coarse_leakage(denseAnalyzed) / max(denseTargetNorm, eps);

% Three probes per virtual coordinate band: first sample, center, last.
probes = struct( ...
    'coordinate_id', {}, 'row', {}, 'column', {}, ...
    'self_gain', {}, 'maximum_cross_talk', {}, ...
    'off_target_l2_ratio', {}, 'coarse_leakage_l2_ratio', {}, ...
    'nullspace_lowpass_l2_ratio', {});
for coordinateIndex = 1:numel(coordinateShapes)
    shape = coordinateShapes{coordinateIndex};
    positions = [ ...
        1, 1; ...
        1 + floor((shape(1) - 1) / 2), ...
            1 + floor((shape(2) - 1) / 2); ...
        shape(1), shape(2)];
    for positionIndex = 1:size(positions, 1)
        target = zero_coordinates(coordinateShapes);
        row = positions(positionIndex, 1);
        column = positions(positionIndex, 2);
        target{coordinateIndex}(row, column) = probeDelta;
        targetRaw = coordinates_to_raw( ...
            target, zero_raw_like(template), h, g, dfilter);
        targetImage = pdfbrec(targetRaw, pfilter, dfilter);
        targetAnalyzed = pdfbdec( ...
            targetImage, pfilter, dfilter, nlevels);
        [observed, nullLowpass, ~] = ...
            raw_to_coordinates(targetAnalyzed, h, g, dfilter);

        observedSelf = observed{coordinateIndex}(row, column);
        observed{coordinateIndex}(row, column) = 0.0;
        maximumCrossTalk = 0.0;
        offTargetSquared = 0.0;
        for otherIndex = 1:numel(observed)
            maximumCrossTalk = max( ...
                maximumCrossTalk, max(abs(observed{otherIndex}(:))));
            offTargetSquared = offTargetSquared + ...
                sum(observed{otherIndex}(:) .^ 2);
        end

        probe = struct();
        probe.coordinate_id = coordinateIds{coordinateIndex};
        probe.row = row - 1;
        probe.column = column - 1;
        probe.self_gain = observedSelf / probeDelta;
        probe.maximum_cross_talk = maximumCrossTalk / probeDelta;
        probe.off_target_l2_ratio = ...
            sqrt(offTargetSquared) / probeDelta;
        probe.coarse_leakage_l2_ratio = ...
            coarse_leakage(targetAnalyzed) / probeDelta;
        probe.nullspace_lowpass_l2_ratio = ...
            nullLowpass / probeDelta;
        probes(end + 1) = probe; %#ok<AGROW>
    end
end

report = struct();
report.schema = 1;
report.prototype_only = true;
report.coordinate_model = ...
    'pdfb_pkva_directional_storage_with_9_7_wfb_nullspace_coordinates';
report.raw_directional_independence_claimed = false;
report.execution_engine = execution_engine();
report.toolbox_path = toolboxPath;
report.function_inventory = functionInventory;
report.parameters = struct( ...
    'pfilter', pfilter, ...
    'dfilter', dfilter, ...
    'nlevels_coarse_to_fine', nlevels, ...
    'cover_size', coverSize, ...
    'required_slots', requiredSlots);
report.capacity = struct( ...
    'coordinate_ids', {coordinateIds}, ...
    'coordinate_shapes', {coordinateShapes}, ...
    'coordinate_counts', coordinateCounts, ...
    'candidate_slots', candidateSlots, ...
    'required_slots', requiredSlots, ...
    'unused_slots', candidateSlots - requiredSlots, ...
    'constructive_rank', candidateSlots, ...
    'rank_certificate', ...
        'three critically sampled 9-7 WFB highpasses at P4 and P3');
report.raw_pdfb_reconstruction_max_abs_error = ...
    max(abs(rawReconstructionError(:)));
report.raw_pdfb_reconstruction_relative_l2_error = ...
    norm(rawReconstructionError(:), 2) / max(norm(image(:), 2), eps);
report.coordinate_chart_reconstruction_max_abs_error = ...
    max(abs(coordinateReconstructionError(:)));
report.coordinate_chart_reconstruction_relative_l2_error = ...
    norm(coordinateReconstructionError(:), 2) / ...
    max(norm(image(:), 2), eps);
report.cover_chart_nullspace_lowpass_l2_ratio = ...
    coverNullLowpass / max(coverCoordinateNorm, eps);
report.cover_chart_max_dfb_roundtrip_l2_ratio = coverDfbRoundtrip;
report.dense_roundtrip = struct( ...
    'coordinate_count', candidateSlots, ...
    'distribution', 'deterministic_rademacher_seed_20260730', ...
    'maximum_absolute_error', denseMaximumAbsoluteError, ...
    'relative_l2_error', denseRelativeL2Error, ...
    'coarse_leakage_l2_ratio', denseCoarseLeakage, ...
    'nullspace_lowpass_l2_ratio', ...
        denseNullLowpass / max(denseTargetNorm, eps), ...
    'maximum_dfb_roundtrip_l2_ratio', denseDfbRoundtrip);
report.independent_writability = struct( ...
    'probe_count', numel(probes), ...
    'minimum_self_gain', min([probes.self_gain]), ...
    'maximum_cross_talk', max([probes.maximum_cross_talk]), ...
    'maximum_off_target_l2_ratio', ...
        max([probes.off_target_l2_ratio]), ...
    'maximum_coarse_leakage_l2_ratio', ...
        max([probes.coarse_leakage_l2_ratio]), ...
    'maximum_nullspace_lowpass_l2_ratio', ...
        max([probes.nullspace_lowpass_l2_ratio]), ...
    'probes', probes);

report.gates = struct( ...
    'capacity_passed', candidateSlots >= requiredSlots, ...
    'raw_pdfb_reconstruction_passed', ...
        report.raw_pdfb_reconstruction_max_abs_error <= 1e-8, ...
    'coordinate_chart_reconstruction_passed', ...
        report.coordinate_chart_reconstruction_max_abs_error <= 1e-8, ...
    'dense_roundtrip_passed', ...
        denseMaximumAbsoluteError <= 1e-8 && ...
        denseRelativeL2Error <= 1e-10, ...
    'self_gain_passed', ...
        report.independent_writability.minimum_self_gain >= 0.99, ...
    'cross_talk_passed', ...
        report.independent_writability.maximum_cross_talk <= 0.01, ...
    'off_target_l2_passed', ...
        report.independent_writability.maximum_off_target_l2_ratio <= 0.05);
gateValues = struct2cell(report.gates);
report.gate_passed = all(cellfun(@(value) logical(value), gateValues));

outputPath = char(options.OutputPath);
if ~isempty(outputPath)
    outputDirectory = fileparts(outputPath);
    if ~isempty(outputDirectory) && ~isfolder(outputDirectory)
        mkdir(outputDirectory);
    end
    stream = fopen(outputPath, 'w');
    assert(stream >= 0, sprintf( ...
        'Could not open output path: %s', outputPath));
    cleanup = onCleanup(@() fclose(stream)); %#ok<NASGU>
    fprintf(stream, '%s\n', jsonencode(report));
end
end


function raw = coordinates_to_raw(coordinates, rawBase, h, g, dfilter)
raw = rawBase;
detailP4 = wfb2rec( ...
    zeros(size(coordinates{1})), ...
    coordinates{1}, coordinates{2}, coordinates{3}, h, g);
detailP3 = wfb2rec( ...
    zeros(size(coordinates{4})), ...
    coordinates{4}, coordinates{5}, coordinates{6}, h, g);
raw{5} = dfbdec_l(detailP4, dfilter, 2);
raw{4} = dfbdec_l(detailP3, dfilter, 2);
end


function [coordinates, maximumNullLowpass, maximumDfbError] = ...
    raw_to_coordinates(raw, h, g, dfilter)
coordinates = cell(1, 6);
nullLowpassSquared = 0.0;
maximumDfbError = 0.0;
rawIndices = [5 4];
coordinateOffsets = [0 3];
for levelIndex = 1:2
    rawIndex = rawIndices(levelIndex);
    detail = dfbrec_l(raw{rawIndex}, dfilter);
    directionalRoundtrip = ...
        dfbrec_l(dfbdec_l(detail, dfilter, 2), dfilter);
    maximumDfbError = max( ...
        maximumDfbError, ...
        norm(directionalRoundtrip(:) - detail(:), 2) / ...
            max(norm(detail(:), 2), eps));
    [lowpass, lh, hl, hh] = wfb2dec(detail, h, g);
    nullLowpassSquared = ...
        nullLowpassSquared + sum(double(lowpass(:)) .^ 2);
    offset = coordinateOffsets(levelIndex);
    coordinates{offset + 1} = lh;
    coordinates{offset + 2} = hl;
    coordinates{offset + 3} = hh;
end
maximumNullLowpass = sqrt(nullLowpassSquared);
end


function raw = zero_raw_like(template)
raw = template;
raw{1} = zeros(size(template{1}));
for levelIndex = 2:numel(template)
    for bandIndex = 1:numel(template{levelIndex})
        raw{levelIndex}{bandIndex} = ...
            zeros(size(template{levelIndex}{bandIndex}));
    end
end
end


function coordinates = zero_coordinates(shapes)
coordinates = cell(size(shapes));
for index = 1:numel(shapes)
    coordinates{index} = zeros(shapes{index});
end
end


function [maximumAbsolute, relativeL2] = ...
    coordinate_error(observed, target)
maximumAbsolute = 0.0;
errorSquared = 0.0;
targetSquared = 0.0;
for index = 1:numel(observed)
    delta = observed{index} - target{index};
    maximumAbsolute = max(maximumAbsolute, max(abs(delta(:))));
    errorSquared = errorSquared + sum(delta(:) .^ 2);
    targetSquared = targetSquared + sum(target{index}(:) .^ 2);
end
relativeL2 = sqrt(errorSquared) / max(sqrt(targetSquared), eps);
end


function value = coordinate_norm(coordinates)
energySquared = 0.0;
for index = 1:numel(coordinates)
    energySquared = energySquared + ...
        sum(double(coordinates{index}(:)) .^ 2);
end
value = sqrt(energySquared);
end


function leakage = coarse_leakage(raw)
energySquared = sum(double(raw{1}(:)) .^ 2);
for rawIndex = 2:3
    for bandIndex = 1:numel(raw{rawIndex})
        energySquared = energySquared + ...
            sum(double(raw{rawIndex}{bandIndex}(:)) .^ 2);
    end
end
leakage = sqrt(energySquared);
end


function set_reproducible_seed(seed)
if exist('OCTAVE_VERSION', 'builtin') ~= 0
    rand('seed', seed); %#ok<RAND>
else
    rng(seed, 'twister');
end
end


function path = canonical_path(value)
[ok, attributes] = fileattrib(value);
if ~ok
    error('Could not canonicalize path: %s', value);
end
path = attributes.Name;
end


function tf = path_is_within(candidate, root)
candidate = strrep(canonical_path(candidate), '\', '/');
root = strrep(canonical_path(root), '\', '/');
if root(end) ~= '/'
    root = [root '/']; %#ok<AGROW>
end
tf = strncmp(candidate, root, length(root));
end


function digest = sha256_file(path)
if exist('OCTAVE_VERSION', 'builtin') ~= 0
    [status, output] = system( ...
        sprintf('sha256sum -- %s', shell_quote(path)));
    assert(status == 0, sprintf( ...
        'sha256sum failed for %s', path));
    tokens = strsplit(strtrim(output));
    digest = lower(tokens{1});
else
    engine = java.security.MessageDigest.getInstance('SHA-256');
    stream = java.io.FileInputStream(java.io.File(path));
    cleanup = onCleanup(@() stream.close()); %#ok<NASGU>
    buffer = zeros(1, 1024 * 1024, 'int8');
    while true
        count = stream.read(buffer, 0, numel(buffer));
        if count < 0
            break;
        end
        engine.update(buffer(1:count));
    end
    raw = typecast(engine.digest(), 'uint8');
    digest = lower(reshape(dec2hex(raw, 2).', 1, []));
end
assert(~isempty(regexp(digest, '^[0-9a-f]{64}$', 'once')), ...
    sprintf('Invalid SHA-256 digest for %s', path));
end


function quoted = shell_quote(value)
quoted = ['''' strrep(value, '''', '''"''"''') ''''];
end


function name = execution_engine()
if exist('OCTAVE_VERSION', 'builtin') ~= 0
    name = ['gnu_octave_' OCTAVE_VERSION];
else
    name = ['matlab_' version('-release')];
end
end
