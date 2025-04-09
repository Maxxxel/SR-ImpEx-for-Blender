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

TBA

---

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