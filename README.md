<div align="center">
  <img src="/sr_impex/assets/images/favicon.png" alt="Favicon">
</div>

# Battleforge Model Importer/Exporter for Blender

A Blender Add-on designed for easy importing and exporting of Battleforge game assets (`.drs`, `.bmg`). Streamline your workflow by quickly importing, editing, animating, and exporting models directly within Blender.

---

## 🚀 Installation

Follow these steps to install the add-on into Blender:

1. Download the latest release (`Battleforge_Blender_*.zip`) from the [Releases](./releases) section.
2. Open Blender.
3. Navigate to `Edit > Preferences > Add-ons`.
4. Click on the `Install...` button.
5. Select the downloaded `.zip` file and click `Install Add-on`.
6. Ensure that the checkbox next to **Battleforge Model Importer/Exporter** is enabled.

---

## 📖 Usage

### Importing Models

1. Open Blender.
2. Go to `File > Import`.
3. Choose the **Battleforge (.drs/.bmg)** file type.
4. Select your desired model file to import.

### Exporting Models

1. **Open Blender**  
   Launch Blender as you normally would.

2. **Import Battleforge Scene**  
   - Go to File > Import > New Battleforge Scene (no file selection needed).

3. **Choose Model Type & Collision**  
   - In the import panel, select:
     - **Model Type**: Static or Animated  
     - **Collision**: Box, Sphere, or Cylinder if required

4. **Create New Battleforge Scene**  
   - Click the **New Battleforge Scene** button.  
   - Blender generates a new Collection hierarchy.

5. **Organize Collections**  
   - (Optional) Delete the original `Collection` hierarchy.  
   - Work within the Battleforge collections.

6. **Rename Your Model Collection**  
   - In the Outliner, rename `DRSModel_object_CHANGENAME` to your model name.

7. **Add Meshes**  
   - Create/import meshes and move them into `Meshes_Collection`.

8. **Assign Materials**  
   - Switch to the Shading workspace.  
   - Open the Asset Browser and under Battleforge Asset Lib, drag-and-drop:
     - **ColNorPar** for Color, Normal, Parameter maps  
     - **ColNorParRef** to include Refraction map  
   - Ensure all wanted texture nodes feed into the **DRS Material** node.

9. **Generate Collision Shapes (optional)**  
   - Add a primitive (Box/Sphere/Cylinder), scale/position around your mesh, and put it inside the right sub-collection.

10. **Export to .drs**  
    - Select your model collection.  
    - Go to File > Export > Battleforge (.drs).  
    - Verify File Name and options:
      - Apply Transform (default)
      - Split Mesh by UV Islands (default)
      - Flip Normals (default): Sometimes your model appears to be inside-out, change this optio to fix it
      - Keep Debug Collection
      - Model Type: static/animated with/without collision
    - Click **Export DRS**.

## 🎯 Supported Features

### ✅ Import Features

- **File Formats**: `.drs`, `.bmg` (objects, units, buildings, and more)
- **Meshes**: Geometry import
- **Materials**: Color, Normal, Metalness, Roughness, Emission, Refraction
- **Skeletons and Skins**: Armature structure and skinning
- **Animations**: Full animation import

### ✅ Export Features

- **File Formats**: `.drs` for static and animated objects
- **Meshes**: Geometry export
- **Materials**: Color, Normal, Metalness, Roughness, Emission, Refraction
- **Animations**: SKA files (editing existing or creating new ones)

---

## 🎥 Showcase

Demonstration of the Battleforge Model Importer for Blender in action:

![Demo](https://i.gyazo.com/e1df80810269e2bb3544f27e174dcf93.gif)

---

## 🔜 Roadmap (Future Development)

- **Animation Smoothing**: Export Battleforge Engine compatible smoothing values for the SKA files.
- **Model Preservation**: Edit models while preserving untouched original data.
- **Fluid Map**: Currently unsupported due to Blender limitations (possible future workaround as a separate animation).

---

## ⚠️ Compatibility & Support

- Compatible with Blender versions `3.x` and `4.x`.  
- Older Blender versions may not be fully supported.

Encountering issues or have suggestions?  
Please report them by opening an issue on the [GitHub repository](./issues).

---

## 📜 License

This project is provided under the MIT License. Refer to the `LICENSE` file for details.