function recovered = gm_decrypt(encrypted, stabilizeHP)
%GM_DECRYPT Invert the interpreted AP/GP/HP mapping from Algorithm 4.

arguments
    encrypted (:,:) double
    stabilizeHP (1,1) logical = true
end

if any(~isfinite(encrypted(:)))
    error("gm_decrypt:Finite", "Encrypted values must be finite.");
end

[rows, cols] = ndgrid(0:size(encrypted,1)-1, 0:size(encrypted,2)-1);
evenPosition = mod(rows + cols, 2) == 0;
oddPosition = ~evenPosition;

recovered = zeros(size(encrypted), "double");
gp = evenPosition & encrypted >= 0 & encrypted <= 32;
apHigh = evenPosition & encrypted >= 193;
apLow = evenPosition & ~gp & ~apHigh;
recovered(gp) = encrypted(gp) * 8;
recovered(apHigh) = 4 * (encrypted(apHigh) - 193);
recovered(apLow) = 10 * (encrypted(apLow) - 50);

hp = encrypted(oddPosition);
if stabilizeHP
    hp = min(max(hp, 0), 2 - 1e-6);
end
if any(abs(2 - hp) < 1e-12)
    error("gm_decrypt:SingularHP", "Inverse HP is singular at value 2.");
end
recovered(oddPosition) = hp ./ (2 - hp);
recovered = min(max(recovered, 0), 255);
end

