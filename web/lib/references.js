import { parseKtmdl } from './ktmdl.js';
import { table } from './binary.js';

export function findAsset(assets, name) {
  return [...assets].find(([key]) => key.toLowerCase() === name.toLowerCase())?.[1];
}

// Select references by their data and matching sidecars, never by character name.
export function inspectReferences(assets) {
  return [...assets]
    .filter(([name]) => /\.model$/i.test(name))
    .map(([name, bytes]) => {
      const stem = name.replace(/\.model$/i, '');
      const result = { name, stem, compatible: false, ready: false, missing: [], error: '' };
      try {
        const model = parseKtmdl(bytes);
        result.model = model;
        result.compatible =
          model.header.boneCount === 33 &&
          model.header.packetCount === 9 &&
          model.names.length === 5 &&
          model.packets.every(
            (p) =>
              p.vd.stride === 48 &&
              JSON.stringify(p.palette) === JSON.stringify(model.packets[0].palette),
          );
        if (!result.compatible)
          result.error =
            'This model can’t be used for conversion: its layout is not supported. Choose another compatible DDR dancer package.';
        result.lookups = [stem + '.b2it', stem + '.grp2it'];
        result.missingLookups = result.lookups.filter((n) => !findAsset(assets, n));
        result.missingTextures = model.names.filter((n) => !findAsset(assets, n));
        result.missing = [...result.missingLookups, ...result.missingTextures];
        if (!result.missingLookups.length && result.compatible) {
          const bones = table(findAsset(assets, result.lookups[0]));
          for (const side of ['Left', 'Right'])
            for (const part of ['Collar', 'Arm', 'ArmRoll', 'ForeArm', 'ForeArmRoll', 'Hand']) {
              if (!bones.some((b) => b.name === side + part && b.index < 33)) {
                result.compatible = false;
                result.error = 'The bone lookup does not match the supported DDR rig.';
              }
            }
        }
        result.ready = result.compatible && result.missing.length === 0;
      } catch (error) {
        result.compatible = false;
        result.ready = false;
        result.error = 'Could not read this DDR model: ' + error.message;
      }
      return result;
    });
}
