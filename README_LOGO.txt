PLACE YOUR LOGO HERE
====================
Put your logo image in this folder named exactly:

    SFBRN_Logo.png

The app looks for assets/SFBRN_Logo.png first. If it is not found,
the report falls back to a styled "SFBRN" text badge and prints a
one-line notice on the cover.

Your master prompt references "SFBRN Logo_No Campus Black.pdf".
Because a PDF cannot be embedded directly as an image, convert its
first page to PNG once and save it here as SFBRN_Logo.png. On Windows
you can do this by opening the PDF, exporting/printing page 1 to PNG,
or using any free PDF-to-PNG converter. Keep the file in this folder
so build_exe.bat bundles it into the installer automatically.

Any organization using the app can also pick a custom logo from the
Settings screen without touching this folder.
