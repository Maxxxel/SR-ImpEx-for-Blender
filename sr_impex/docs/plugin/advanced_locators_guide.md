# Locator Editor

Locators are attachment points for effects, projectiles, health bars and model parts.

## Edit a locator

1. Select your model and open **DRS Editor → Locator Editor**.
2. Select a locator in the list, or click **+** beside the list and choose its type.
3. Choose **Attach to**. For a resource locator, select its **Effect** or **Resource**.
4. Click **Apply Changes**.
5. Move or rotate the marker in the viewport, then click **Save Placement**.
6. Save your `.blend` and export the model.

The list stays short; scroll to see more entries. **−** beside the list removes the selected locator record and its marker. Only relevant fields appear below the list. Hover over **Attach to** for a description of each choice.

Changing an attachment starts the locator at its new attachment's origin. Changing only its type or filename keeps its placement. Apply pending detail edits before saving placement.

## Choose an attachment

| Choice | What it means |
| --- | --- |
| **Model** | Moves with the model, without following a particular bone. |
| **Skeleton** | Gives the effect access to the model's skeleton, so the effect can use its own bone links. |
| **Bone** | Follows the bone you choose. |

For imported models, keep the original attachment unless you intend to change it. **Skeleton** does not mean the first or root bone. Firedancer uses it for one persistent effect whose internal emitters attach to her head and hands.

The old checkbox stored **Model as -1** and **Skeleton as -2**. These are real engine attachment modes. The new names replace the numeric checkbox; imported values are preserved.

## Choose and preview an effect

1. Configure **Skylords Reborn Folder** in the add-on preferences. See the [Effects Guide](advanced_effects_guide.md).
2. Select a **Persistent Figure FX** or **Persistent Building FX** locator.
3. Click the search icon beside **Effect** to open **Effect Selector**. Search by name or choose a category.
4. **Preview** auditions the resource. **Use Resource** updates the draft filename; **Cancel** keeps the previous one.
5. Click **Apply Changes**, then **Update Preview**. Press **Space** to play the timeline.

**Audio** and **Live Update** sit below the preview button. Live Update refreshes resource edits after you pause editing. **×** beside Update Preview clears the model's generated FX and audio. State-triggered effects require the corresponding game state; they are not automatically played as persistent effects.

Firedancer's Idle fire comes from her persistent locator, not an Idle EffectSet entry. It can play without an animation event.

Categories are filename hints. The source effect files remain external assets; assigning a reference does not copy them into the DRS. Create or edit effects in the external Effect Editor.

## Placement and export

- Use **+**, rather than duplicating marker objects. Duplicated markers can share the same internal identity.
- Use **Save Placement** after moving or rotating markers. Export uses saved locator data, not unsaved viewport movement.
- Deleting a marker alone does not remove its saved locator. Use **−** beside the list.
- Module references can show imported model parts. Changing a filename does not automatically rebuild construction geometry.
- Preserve imported unknown types. IDs 14 and 15 are not offered for new locators.
- Test attachments through representative animations and in the Map Editor after export.

## Common problems

| Problem | Check |
| --- | --- |
| No locator list | Select a mesh or collection belonging to the intended model. |
| A bone attachment cannot be selected | Import the model's skeleton first. |
| A marker moves to the origin | Changing attachment resets placement. Position it afterward and Save Placement. |
| A locator returns after deleting its marker | Remove the record with **−** beside the list. |
| Export uses an old position | Save Placement before exporting. |
| The effect is missing | Check the library path and resource filename, then Update Preview. Game-state FX may require their activation state. |

See the [Effects Guide](advanced_effects_guide.md) for animation-triggered effects and sounds, and the [Unit Creation Guide](unit_creation_buide.md) for the full workflow.
