function report = probe_pdfb_projection_consistency(varargin)
%PROBE_PDFB_PROJECTION_CONSISTENCY Test a projected PDFB coordinate write.
%
% For a redundant PDFB, analysis(synthesis(c + e_i)) need not equal c+e_i.
% This diagnostic solves the eligible-band block system B*z=t by Richardson
% residual correction, where B is analysis(synthesis(.)) restricted to the
% eligible directional bands.  It does not change the final gate thresholds.

parser = inputParser;
addParameter(parser, 'ToolboxPath', '', @(x) ischar(x) || isstring(x));
addParameter(parser, 'PFilter', '9-7', @(x) ischar(x) || isstring(x));
addParameter(parser, 'DFilter', 'pkva', @(x) ischar(x) || isstring(x));
addParameter(parser, 'NLevels', [2 2 2 2], ...
    @(x) isnumeric(x) && isvector(x) && ~isempty(x));
addParameter(parser, 'EligibleLevel', 4, ...
    @(x) isnumeric(x) && isscalar(x) && isfinite(x));
addParameter(parser, 'ProbeFraction', 0.5, ...
    @(x) isnumeric(x) && isscalar(x) && x > 0 && x < 1);
addParameter(parser, 'ProbeDelta', 1.0, ...
    @(x) isnumeric(x) && isscalar(x) && isfinite(x) && x > 0);
addParameter(parser, 'Iterations', 12, ...
    @(x) isnumeric(x) && isscalar(x) && x >= 1 && x == floor(x));
addParameter(parser, 'Relaxation', 1.0, ...
    @(x) isnumeric(x) && isscalar(x) && isfinite(x) && x > 0);
parse(parser, varargin{:});
options = parser.Results;

toolboxPath = char(options.ToolboxPath);
assert(isfolder(toolboxPath), 'PDFB:ProjectionToolboxMissing', ...
    'Contourlet Toolbox directory does not exist: %s', toolboxPath);
addpath(genpath(toolboxPath), '-begin');
nlevels = double(options.NLevels(:).');
eligibleLevel = double(options.EligibleLevel);
eligibleCellIndex = eligibleLevel + 1;
probeDelta = double(options.ProbeDelta);
iterations = double(options.Iterations);
relaxation = double(options.Relaxation);

coverSize = 512;
[rows, columns] = ndgrid(uint32(0:coverSize - 1), ...
    uint32(0:coverSize - 1));
imageUint8 = uint8(mod( ...
    rows .* uint32(37) + columns .* uint32(19) + ...
    mod(rows .* columns, uint32(251)), ...
    uint32(256)));
image = double(imageUint8);

pfilter = char(options.PFilter);
dfilter = char(options.DFilter);
coefficients = pdfbdec(image, pfilter, dfilter, nlevels);
baselineImage = pdfbrec(coefficients, pfilter, dfilter);
baselineRoundTrip = pdfbdec( ...
    baselineImage, pfilter, dfilter, nlevels);
eligible = coefficients{eligibleCellIndex};
baselineEligible = baselineRoundTrip{eligibleCellIndex};

probes = struct( ...
    'band_id', {}, ...
    'row', {}, ...
    'column', {}, ...
    'iterations', {}, ...
    'self_gain', {}, ...
    'maximum_cross_talk', {}, ...
    'off_target_l2_ratio', {}, ...
    'residual_l2_ratio', {}, ...
    'synthesis_correction_l2_ratio', {}, ...
    'synthesis_correction_max_abs_ratio', {});
for bandIndex = 1:numel(eligible)
    band = eligible{bandIndex};
    row = 1 + floor(options.ProbeFraction * (size(band, 1) - 1));
    column = 1 + floor(options.ProbeFraction * (size(band, 2) - 1));
    target = zero_like_bands(eligible);
    target{bandIndex}(row, column) = probeDelta;
    correction = zero_like_bands(eligible);
    residual = target;
    for iteration = 1:iterations
        correction = add_scaled_bands( ...
            correction, residual, relaxation);
        observed = projected_delta( ...
            coefficients, correction, baselineEligible, ...
            eligibleCellIndex, pfilter, dfilter, nlevels);
        residual = subtract_bands(target, observed);
    end

    observed = projected_delta( ...
        coefficients, correction, baselineEligible, ...
        eligibleCellIndex, pfilter, dfilter, nlevels);
    observedTarget = observed{bandIndex}(row, column);
    maximumCrossTalk = 0.0;
    offTargetSquared = 0.0;
    residualSquared = 0.0;
    correctionSquared = 0.0;
    correctionMaxAbs = 0.0;
    for otherBandIndex = 1:numel(observed)
        observedBand = observed{otherBandIndex};
        targetBand = target{otherBandIndex};
        residualBand = targetBand - observedBand;
        residualSquared = residualSquared + sum(residualBand(:) .^ 2);
        correctionBand = correction{otherBandIndex};
        correctionSquared = correctionSquared + ...
            sum(correctionBand(:) .^ 2);
        correctionMaxAbs = max( ...
            correctionMaxAbs, max(abs(correctionBand(:))));
        if otherBandIndex == bandIndex
            observedBand(row, column) = 0.0;
        end
        maximumCrossTalk = max( ...
            maximumCrossTalk, max(abs(observedBand(:))) / probeDelta);
        offTargetSquared = offTargetSquared + sum(observedBand(:) .^ 2);
    end

    probe = struct();
    probe.band_id = sprintf('P%d:D%d', eligibleLevel, bandIndex - 1);
    probe.row = row - 1;
    probe.column = column - 1;
    probe.iterations = iterations;
    probe.self_gain = observedTarget / probeDelta;
    probe.maximum_cross_talk = maximumCrossTalk;
    probe.off_target_l2_ratio = sqrt(offTargetSquared) / probeDelta;
    probe.residual_l2_ratio = sqrt(residualSquared) / probeDelta;
    probe.synthesis_correction_l2_ratio = ...
        sqrt(correctionSquared) / probeDelta;
    probe.synthesis_correction_max_abs_ratio = ...
        correctionMaxAbs / probeDelta;
    probes(end + 1) = probe; %#ok<AGROW>
end

report = struct();
report.schema = 1;
report.diagnostic_only = true;
report.backend_label = 'minh_do_contourlet_toolbox_pdfb_projected_v1';
report.execution_engine = execution_engine();
report.pfilter = pfilter;
report.dfilter = dfilter;
report.nlevels = nlevels;
report.eligible_level = eligibleLevel;
report.probe_fraction = options.ProbeFraction;
report.probe_delta = probeDelta;
report.iterations = iterations;
report.relaxation = relaxation;
report.minimum_self_gain = min([probes.self_gain]);
report.maximum_cross_talk = max([probes.maximum_cross_talk]);
report.maximum_off_target_l2_ratio = ...
    max([probes.off_target_l2_ratio]);
report.maximum_residual_l2_ratio = max([probes.residual_l2_ratio]);
report.maximum_synthesis_correction_l2_ratio = ...
    max([probes.synthesis_correction_l2_ratio]);
report.maximum_synthesis_correction_max_abs_ratio = ...
    max([probes.synthesis_correction_max_abs_ratio]);
report.probes = probes;
end


function bands = zero_like_bands(template)
bands = cell(size(template));
for index = 1:numel(template)
    bands{index} = zeros(size(template{index}));
end
end


function output = add_scaled_bands(left, right, scale)
output = cell(size(left));
for index = 1:numel(left)
    output{index} = left{index} + scale .* right{index};
end
end


function output = subtract_bands(left, right)
output = cell(size(left));
for index = 1:numel(left)
    output{index} = left{index} - right{index};
end
end


function observed = projected_delta( ...
    coefficients, correction, baselineEligible, ...
    eligibleCellIndex, pfilter, dfilter, nlevels)
modified = coefficients;
for index = 1:numel(correction)
    modified{eligibleCellIndex}{index} = ...
        modified{eligibleCellIndex}{index} + correction{index};
end
modifiedImage = pdfbrec(modified, pfilter, dfilter);
roundTrip = pdfbdec(modifiedImage, pfilter, dfilter, nlevels);
roundTripEligible = roundTrip{eligibleCellIndex};
observed = cell(size(roundTripEligible));
for index = 1:numel(roundTripEligible)
    observed{index} = ...
        double(roundTripEligible{index}) - ...
        double(baselineEligible{index});
end
end


function name = execution_engine()
if exist('OCTAVE_VERSION', 'builtin') ~= 0
    name = ['gnu_octave_' OCTAVE_VERSION];
else
    name = ['matlab_' version('-release')];
end
end
