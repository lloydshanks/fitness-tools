# Fitness Tools Notes

This is a set of tools that I use to help manage fitness data.

The first tool "mywellness2tcx_pandas.py" is used to take MyWellness (Technogym) files, convert them into a TCX file, ready for upload into Garmin Connect or Strava.

## MyWellness to TCX (Pandas)

This code is based on the code written by Denis Otkidach found here -> https://github.com/ods/mywellness2tcx, thank you Denis!

I have changed this code to use Pandas and LXML to to bring in heart rates. Heart Rates aren't picked up at the same interval (5 seconds) as bike data so I have used a SciPy interpolation to fill in the required data.

There are some other improvements to this base code to include running found here:

- https://github.com/marcin-gryszkalis/mywellness2tcx/blob/master/mywellness2tcx.py
- https://github.com/macschlingel/mywellness2tcx

### How to fetch JSON file from MyWellness

- Open https://mywellness.com/cloud/Training/
- In Safari open the Develop menu and select Show Web Inspector
- Click the Source tab and then click into the activity page you want to export
- Click into the activity itself from the summary page (you shuold now see the Power/Cadense/Speed/Hear Rate data)
- Under PerformedWorkoutSession there should be a folder called XHRs, expand this
- Click Details and copy all the JSON from the main window and save this in a local file

### TCX Export from Strava

To ensure that the TCX file would work well we Strava I exported and activity from Strava by performing the following.

Strava allows you to export TCX (Training Center XML) versions of your own activities. TCX files contain more information than GPX files such as heart rate, cadence, and watts. TCX files exported from Strava will also contain power data. TCX export only works for activities with GPS data, which may exclude indoor activities with no GPS.

This is a little-known trick, however, it's simple to use. Simply add "/export_tcx" - without quotes - to the end of your activity page URL. For example, if your activity page is www.strava.com/activities/2865391236 - just add the text to give you www.strava.com/activities/2865391236/export_tcx and hit enter. This will download a TCX version of your file to the location specified by your browser's preferences.
