"""Generate independent Astropy TAN reference vectors in memory for JS QA.

These are mathematical coordinate test vectors, not observation data. No
reference files are saved or shipped with the application.
"""
import json

from astropy.wcs import WCS

centers = [
    (0.0, 0.0), (359.999, 0.0), (0.001, -20.0), (133.75921, -7.24216),
    (269.4463, 4.7676), (331.0962, -56.8005), (248.1674, 66.7548),
    (20.0, 85.0), (20.0, -85.0), (20.0, 89.9), (20.0, -89.9),
    (0.0, 90.0), (20.0, 90.0), (359.99, 90.0), (20.0, -90.0),
    (359.99, -90.0), (359.999, 89.999999), (0.001, -89.999999),
]
samples = [0.0, 0.5, 30.5, 119.5, 120.0, 120.5, 209.5, 239.5, 240.0]
result = []
for ra, dec in centers:
    wcs = WCS(naxis=2)
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    wcs.wcs.crval = [ra, dec]
    wcs.wcs.crpix = [120.5, 120.5]
    wcs.wcs.cdelt = [-3.075 / 3600, 3.075 / 3600]
    grid = {
        "crval1": ra, "crval2": dec, "crpix1": 120.5, "crpix2": 120.5,
        "cdelt1": -3.075 / 3600, "cdelt2": 3.075 / 3600,
        "width": 240, "height": 240,
        "pixel_scale_arcsec": 3.075, "native_pixel_scale_arcsec": 6.15,
    }
    points = []
    for x in samples:
        for y in samples:
            # Browser pixels have centers i+0.5 and top-to-bottom rows;
            # Astropy uses centers i and bottom-to-top FITS rows.
            ra_point, dec_point = wcs.pixel_to_world_values(x - 0.5, 239.5 - y)
            points.append({"x": x, "y": y, "ra": float(ra_point), "dec": float(dec_point)})
    result.append({"wcs": grid, "points": points})
print(json.dumps(result, allow_nan=False))
