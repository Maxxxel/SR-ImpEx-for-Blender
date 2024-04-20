# Battleforge Model Importer/Exporter for Blender

## Features:
    Supports *.drs and *.bmg files
    Import Meshes
    Import Materials (Color, Normal, Metalness, Roughness, Refraction)
    Import Skeleton
    Import Skin
    Import Animations
    Export Static Objects
    
## What's up next?
    Export Models (different types)
    Fix Bugs (There are a lot :D)
    ... Suggestions?
    
## Showcase
Here is a quick demonstration of the Battleforge Model Importer/Exporter for Blender in action:

![Demo](https://i.gyazo.com/e1df80810269e2bb3544f27e174dcf93.gif)

## Installation
1. Download latest Battleforge_Blender_*.zip from the Releases section of the repository.
2. Launch Blender
3. Go to Edit > Preferences.
4. Click on the Add-ons tab.
5. Click on the Install button.
6. Navigate to the downloaded zip file and select it.
7. Click on the Install Add-on button.
8. Make sure the checkbox next to Battleforge Model Importer/Exporter is checked to enable the add-on.

## Usage
1. Open Blender
2. Go to File > Import
3a. Select the Battleforge file type if you want to import a Battleforge Model.
3b. Select the New Battleforge Scene if you want to create a new Battleforge Model.
5. Follow the prompts to customize your import settings.

## Export Models
### Follow the strict Structure
1. Create a Collection called "DRSModel_YOUR_MODEL_NAME_Static (replace YOUR_MODEL_NAME with your model's name)
2. Create a node called "CDspMeshFile*"
3. Create your Meshes underneath this node
4. For Materials you can press ctrl + a and type 'drs' to set the DRS Material Node
5. Maybe add a new node called "CollisionShape"
6. add new Collision shape objects underneath this node
7. Use Cylinder, Sphere or Box as Name and type of the collisions hape object/mesh

## Notes
This add-on is only compatible with Blender 4.0 and may not work with other versions of Blender. If you encounter any issues or have any feedback, please submit an issue on the GitHub repository.

Inside the resources folder you can find an example export blend file that worked for me.