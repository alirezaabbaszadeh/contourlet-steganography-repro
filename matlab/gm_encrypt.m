function encrypted = gm_encrypt(secret, mode)
%GM_ENCRYPT Interpreted AP/GP/HP mapping from Algorithm 1.
%
% The paper leaves CODE_HP undefined for odd-parity values above 32.
% mode="strict" raises on those pixels; mode="interpreted" applies the
% printed HP equation to every odd-parity pixel.

arguments
    secret (:,:) double
    mode (1,1) string {mustBeMember(mode, ["interpreted","strict"])} = "interpreted"
end

if any(secret(:) < 0 | secret(:) > 255 | ~isfinite(secret(:)))
    error("gm_encrypt:Range", "Secret values must be finite and in [0,255].");
end

[rows, cols] = ndgrid(0:size(secret,1)-1, 0:size(secret,2)-1);
evenPosition = mod(rows + cols, 2) == 0;
oddPosition = ~evenPosition;
integerSecret = round(secret);
inL1 = integerSecret >= 1 & mod(integerSecret - 1, 3) == 0;

if mode == "strict" && any(oddPosition & secret > 32, "all")
    error("gm_encrypt:UndefinedHP", ...
        "Algorithm 1 leaves CODE_HP undefined above 32.");
end

encrypted = zeros(size(secret), "double");
gp = evenPosition & inL1;
ap = evenPosition & ~inL1;
encrypted(gp) = secret(gp) / 8;
encrypted(ap) = secret(ap) / 10 + 50;
encrypted(oddPosition) = 2 * secret(oddPosition) ./ (1 + secret(oddPosition));
end

