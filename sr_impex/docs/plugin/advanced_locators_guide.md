# Advanced Locators Guide

Locators describe attachment points and functional positions: a health-bar offset, a projectile origin, a bone-following effect, or a referenced module. This guide covers editing those entries, preserving their coordinate spaces, and getting scene changes into the exported `CDrwLocatorList`.

> **Two rules prevent most export mistakes:** the model collection's saved locator data, not viewport geometry, is exported; and bone-attached locators must remain attached to their bones, not be reparented directly to `GameOrientation`.

## Before You Start

- Start with an imported, working asset of the same kind whenever possible. Preserve its skeleton, locator types, and resource-reference conventions until replacements have been verified in-game.
- Make the **top-level** `DRSModel_<basename>` collection the active **Layer Collection** in the Outliner. Selecting a mesh, armature, or `SLocators_Collection` is not equivalent.
- Open the 3D Viewport sidebar (**N**) → **DRS Editor** → **CDrwLocatorList**.
- Keep the model's armature, and `GameOrientation` if used, inside this model's collection tree. The editor finds the first armature whose name does not contain `Control_Rig`; multiple candidate armatures can make attachment ambiguous.
- Keep a saved `.blend` backup before changing attachment rules or deleting entries.

### Which export types contain locators?

The current `WriteOrder` includes `CDrwLocatorList` for **AnimatedUnit**. The listed static/animated object and building export types do **not** include this block. Creating locator markers or a blob does not add a locator block to those formats automatically. A model's appearance or its use as a building does not, by itself, establish support for unit-style locators.

For buildings, distinguish locator attachments from [effects and audio](advanced_effects_guide.md), construction data, and the building's own mesh/state setup. Follow the [Building Creation Guide](building_creation_guide.md) and the requirements of a matching working asset rather than changing the export type solely to obtain locators.

## Locator Types: Choose a Role, Not a Required Set

These are the exact **Type** labels exposed by the editor. Their names describe intended roles; the add-on does not validate the game's requirements for a particular asset. Not every unit needs every type, and a type label alone does not make the associated gameplay behavior work.

| ID | Type | Practical role / authoring guidance |
| --- | --- | --- |
| 0 | `HealthBar` | A position for the health-bar/UI offset. Start from the placement of a comparable working unit. |
| 1 | `DestructiblePart` | Attachment for a referenced destructible module; the importer can load its static BMS mesh preview. |
| 2 | `Construction` | Construction-related point; preserve the reference asset's usage rather than assuming a universal setup. |
| 3 | `Turret` | Turret-related entry. In the current importer, a non-empty **File** is loaded as an SKA animation on the model's armature, not as a generic turret mesh. |
| 4 | `FxbIdle` | Idle-effect role. Verify the referenced effect and activation behavior against the asset. |
| 5 | `Wheel` | Wheel/module attachment; the importer attempts to load an animated BMS module and its animations. |
| 6 | `StaticPerm` | Static permanent-effect role; retain the working asset's conventions. |
| 7 | `Unknown7` | Unresolved role. Preserve existing entries unless their behavior is known. |
| 8 | `DynamicPerm` | Dynamic permanent-effect role; check attachment and resource behavior in-game. |
| 9–13 | `DamageFlameSmall`, `DamageFlameSmallSmoke`, `DamageFlameLarge`, `DamageSmokeOnly`, `DamageFlameHuge` | Damage-effect positions. These labels are not a requirement to add all five. |
| 14–16 | `SpellCast`, `SpellHitAll`, `Hit` | Spell/cast/hit-related positions; match the asset's actual effect and animation setup. |
| 29 | `Projectile_Spawn` | Projectile-origin position/orientation where the game uses this role. Confirm direction and timing in-game. |

### What belongs in File?

**File** becomes the locator's `file_name` string. It is a resource reference, not a sound-event editor or an automatic resource-packaging step.

- Leave it empty when the locator only defines a position and the asset does not require a resource there.
- Use the exact resource name/path expected by a working asset and the game. The editor stores the text as entered; it does not validate, copy, or convert the referenced resource. Do not assume Blender's file picker turns an absolute disk path or a `//` path into a usable game reference.
- For `DestructiblePart` and `Wheel`, the current preview loaders resolve the reference relative to the imported DRS directory. A trailing `.module` is replaced with `.bms`, and the BMS supplies the referenced DRS mesh/state data.
- For `Turret`, the current importer passes a non-empty reference to the SKA animation reader relative to the DRS directory. Do not substitute an arbitrary `.module` because the type sounds like a model attachment.
- `.fxb` references can describe effects, but the locator importer does not currently build their effect visualization. A marker sphere is not evidence that the effect resource was found or will run.
- Configure audio variants such as `.snr`/`.wav`, sound types, and animation-keyed events in the **EffectSet** workflow, not by placing an audio filename in a locator. See the [Advanced Effects Guide](advanced_effects_guide.md).

No concrete game resource filenames are prescribed here: use references verified in the installed/extracted assets being targeted.

## A Reliable Editing Workflow

### 1. Create or choose an entry

1. Activate the correct top-level `DRSModel_<basename>` collection and open **CDrwLocatorList**.
2. Click **Add**, choose **Type** in the dialog, and confirm; or select an existing row.
3. Select the intended row explicitly. Selecting a row selects its matching scene object when one exists.

New entries start with an empty **File**, no bone attachment, zero position, and identity rotation. The editor normally creates a small mesh sphere named `Locator_<Type>` under `SLocators_Collection`; locators are not necessarily Blender Empty objects. Imported module previews can instead be meshes or armatures.

> **Sync existing viewport edits before Add or another detail update.** These operations reapply saved data to the model's locators, so unsaved scene offsets on other entries can be overwritten too.

### 2. Set metadata and attachment before positioning

Under **Selected Locator**:

1. Choose **Type** and enter **File**, if applicable.
2. If the locator must follow a bone, choose it in **Parent**. If it is a model-root point, leave **Parent** empty.
3. Click **Update parent and remove transformations** to commit those fields.

**This button resets the selected entry's stored position to zero and rotation to identity every time**, even if the parent did not change or only **File** was edited. A bone locator resets to its bone-local origin; a non-bone locator resets to the game-space origin, displayed through `GameOrientation` when available. It is not a keep-world-transform reparent command or Blender's Apply Transforms command.

The optional popup editor also shows **Position (view)**. It is not the placement workflow: the update operator resets position rather than saving an entered offset. Position the actual scene object after the detail update.

### 3. Position the scene object, then save its transform

1. Select the matching locator marker or module root in the viewport/Outliner.
2. Move and rotate it to the required point. Keep the intended parent and avoid introducing scale as a substitute for placement.
3. For a bone attachment, scrub relevant animations and check that the point follows the correct bone.
4. Reactivate the top-level `DRSModel_<basename>` collection if selecting a child changed the active Layer Collection.
5. Click **Sync from Scene**. This captures scene transforms into the saved locator data and reapplies the attachment rules.
6. Save the `.blend` file after synchronizing.

If metadata must change later, expect the update button to reset the offset: note the intended placement, commit the metadata, reposition the object, and sync again.

### 4. Remove through the editor

Use **Remove** for an entry that should not export. It removes the saved entry and its matching scene object. Deleting only a viewport marker does not remove the saved entry; synchronization can recreate it.

## GameOrientation and Attachment Spaces

`GameOrientation` (**GO**) is the model's game/display-space helper, not an export prerequisite or a universal replacement for bone parenting. The standard conversion includes a Y-axis mirror and rotations about X and Z, so treating it as only an ordinary rotation can produce incorrect offsets.

> **Good practice, not mandatory ordering:** establish the model hierarchy early to make its coordinate spaces easier to reason about. Modeling first and then **parent → correct rotation → apply the relevant mesh transforms** is also a supported workflow; check the resulting game-space orientation and resync locator placement afterward. Not every mesh needs a direct GO parent: imported armature hierarchies and bone-locator relationships should remain intact.

That mesh workflow is not a reason to apply transforms blindly to locator markers or imported armatures. Sync reads a locator's **object transform**, not the position/orientation baked into its sphere's vertices. Place/rotate the locator object and sync it; baking that placement into the marker mesh can lose the intended exported point.

| Locator attachment | Scene representation used by the editor | What Sync from Scene records |
| --- | --- | --- |
| No bone; GO found | Object parent is `GameOrientation`; saved game-space transform is displayed through GO. | For a **direct GO child**, removes GO's world transform from the object's world transform and stores game-space position/3×3 matrix; normally `bone_id = -1`. |
| Valid bone | Object parent is the armature, with `parent_type = BONE` and the selected bone. The armature may itself sit under GO. | Object-local location and `matrix_basis` 3×3 matrix; the parent bone's index in that armature's bone list. GO is not stripped separately from this local offset. |
| No bone and no recognized GO parent | No helper conversion is applied during capture. | The object's world transform is stored directly. An arbitrary parent or indirect GO ancestor is not treated as the direct-GO case. |

The editor materializes a non-bone entry by multiplying its saved game-space transform by GO's world matrix; it captures a direct GO child's transform using the inverse operation. With no GO helper, those saved values are used as world-space values instead.

**Do not manually parent every locator to GO.** Set attachment through **Parent** and the update button. Bone-following points must remain bone-attached; otherwise Sync will classify them as non-bone and lose that attachment. For a new manually created non-bone marker, establish its intended game-space placement before syncing; merely using “Keep Transform” to reparent can preserve the wrong space.

The locator editor searches for the **exact object name** `GameOrientation` inside the active model's collection tree. A helper renamed to `GameOrientation.001` is not found by this lookup. This matters when multiple models are imported into one scene. Resolve helper naming/model isolation deliberately; do not compensate by rotating every locator or changing bone parents.

### The special -2 option

When an armature exists and **Parent** is empty, the editor exposes **If None set Parent to -2**. Committing the update writes `bone_id = -2` instead of `-1`; the option is described as allowing attachment to a bone specified in an effect. It is still a non-bone entry in Blender, not a selection of bone index 2.

Use it only when the target asset/effect calls for it. For an imported `-2` entry, confirm the checkbox and commit it before positioning and syncing: import stores the numeric ID, whereas non-bone Sync chooses `-2` from the saved checkbox flag. As with other detail updates, committing the option resets the offset.

## Exactly What Sync from Scene Does

**Sync from Scene** scans recursively through the active model collection, not just the selected marker or `SLocators_Collection`. It recognizes objects with the `_cdrw_uid` custom property or names beginning with `Locator_`.

- Matches existing entries by `_cdrw_uid`; assigns UIDs and appends entries for newly recognized objects.
- Records bone-local transforms for actual bone parents; otherwise records the non-bone transform according to the GO rules above.
- Updates `class_id` from an object's `_class_id` property when present. For a newly discovered marker without saved metadata, it infers the class from an exact `Locator_<Type>` name, otherwise defaults to `HealthBar`.
- Retains an existing entry's **File**; it does **not** read a resource reference from the object's `_file` property. New scene-discovered entries start with an empty **File**.
- Never removes saved entries merely because their scene objects were deleted.
- Reapplies saved data to the scene and refreshes the list after capture.

Changing **Type**, **File**, **Parent**, or the `-2` checkbox in the UI is not committed by Sync. Use **Update parent and remove transformations**, then place the object and sync. Use **Add** rather than duplicating a locator object: duplicating its UID can make two objects compete for one saved entry. Renaming an existing marker does not replace its saved type/file metadata.

## Persistence, Previews, and Export

The authoritative data is the `CDrwLocatorListJSON` custom property on the **model collection**. It contains the version and locator entries, including their UIDs, class IDs, resource strings, bone IDs, position, rotation matrix, and preserved unknown integer. UIDs connect this data to scene objects; they are not exported as gameplay identifiers.

- DRS import saves the blob before optional module/locator visualization. Disabling **Import Modules/Locators** can leave valid locator data with no visible markers.
- Simply opening the list reads the saved data; it does not build missing previews. Sync can materialize missing objects, but it first captures any recognized objects already present, so use a backup and inspect the result.
- **Add**, the detail update, and Sync materialize generic marker spheres when no matching object exists. They do not rebuild a referenced BMS module or an FXB simulation just because **File** changed.
- With **Import Modules/Locators** enabled, `DestructiblePart`/`Wheel` can load module previews. A non-empty `Turret` reference loads animation and returns without creating its own locator marker. Missing referenced files may cause import failures; preserving the blob does not supply those files.
- Export copies the blob to its working collection and converts that saved data to `SLocator` entries when the selected export type includes `CDrwLocatorList`. It does **not** perform an automatic scene sync or discover markers as a fallback.
- Missing locator data produces an empty list with a warning; malformed JSON is not a supported recovery path. Reimport a working source or restore a backup rather than hand-editing an uncertain blob.

A sphere moving correctly in Blender proves only the scene attachment. Resource availability, effect activation, projectile direction, and gameplay behavior still need a matching game asset and an in-game check.

## Troubleshooting

| Symptom | Check / correction |
| --- | --- |
| **No valid DRSModel selected.** | Make a direct child of the scene named `DRSModel_<basename>` the active Layer Collection. A nested model collection or selected object is insufficient. |
| **No armature in this model** or no **Parent** field | Ensure the intended armature is inside this model's collection tree and is not a `Control_Rig`. Do not pick an unrelated preview armature. |
| Locator snaps to an origin after updating | Expected: the detail update resets stored translation/rotation. Place it afterward and use Sync. Sync other pending edits before any operation that reapplies the blob. |
| Bone-following point becomes static | Check actual bone parenting, not just the UI's pending **Parent** value. Commit the parent, reposition, and sync; do not reparent the point directly to GO. |
| Offset is rotated/mirrored, or differs after Sync | If GO is used, check its exact name and direct non-bone parenting; otherwise confirm the intended world/game-space values. Do not apply a second conversion or strip GO from a bone-local offset. |
| File/type edit disappears or exports unchanged | Commit with **Update parent and remove transformations**. Sync captures scene data, not unsaved UI metadata or `_file`. Reposition after committing. |
| Deleted locator returns | Use **Remove**; scene deletion alone leaves the saved entry intact. |
| Duplicate or unexpected `HealthBar` entries | Inspect manually named `Locator_*` objects and duplicated UIDs. Prefer **Add**; new name inference requires an exact type label, not an arbitrary name or `.001` suffix. |
| A `-2` attachment becomes `-1` after Sync | Commit **If None set Parent to -2** before repositioning/syncing. The non-bone capture uses the saved option flag. |
| Entry exists but has no marker, module, or effect preview | Check import options and the type-specific preview behavior above. A missing preview does not imply a missing saved entry. |
| Export ignores viewport edits or all locators | Sync the correct model first; verify its blob and that the chosen export type actually includes `CDrwLocatorList`. There is no marker-scan export fallback. |
| Bone attachment is wrong after skeleton changes | The editor stores bone-list indices; import resolves stored skeleton identifiers. Keep the working skeleton mapping stable and revalidate attachments after bone additions/reordering. |

## Checklists

### Before placement

- [ ] The intended top-level `DRSModel_<basename>` is active.
- [ ] The export type supports the locator block.
- [ ] Each chosen type serves an asset-specific purpose; no unverified “required set” was added.
- [ ] Resource references come from verified assets; audio is configured in EffectSet instead.
- [ ] Parent/type/file changes have been committed before positioning.

### Before export

- [ ] Bone locators are still attached to the intended bones; non-bone placement uses the intended GO or world/game-space convention.
- [ ] If GO is used, its helper naming is unambiguous; the model's armature lookup is also unambiguous.
- [ ] Placement/orientation has been checked through representative animations.
- [ ] **Sync from Scene** has captured final placement on the correct model.
- [ ] Unwanted entries were removed through **Remove**, with no duplicate UIDs remaining.
- [ ] The `.blend` was saved after synchronization, and referenced resources are available separately.
- [ ] Reimport/export placement and the intended in-game behavior have been checked; viewport previews alone were not treated as validation.

## Related Guides and Implementation References

- [Unit Creation Guide](unit_creation_buide.md)
- [Object Creation Guide](object_creation_guide.md)
- [Building Creation Guide](building_creation_guide.md)
- [Advanced Effects Guide](advanced_effects_guide.md)
- [Advanced Abilities Guide](advanced_abilities_guide.md)
- [CDrwLocatorList / SLocator format notes](../drs/cdrwlocatorlist.md)
- [Skeleton format notes](../drs/cskskeleton.md)
- [Locator editor](../../blender/editors/locator_editor.py): active model selection, UI actions, UID matching, GO/bone capture and materialization.
- [DRS import/export](../../utilities/drs_utility.py): `persist_locator_blob_on_collection`, `process_slocator_import`, module loaders, `create_cdrw_locator_list`, and export blob copying.
- [Transform helpers](../../blender/transform_utils.py): `get_conversion_matrix` and `parent_under_game_axes`.
- [Locator definitions](../../definitions/locator_definitions.py) and [type/export-order definitions](../../definitions/enums.py).

Where older format notes describe Empty-only markers or a scene-scan export fallback, use the current implementation behavior documented here.