## 0.6.1 (2025-02-05)

### Fix

- **band**: fixes bug on inconsistent band value stack
- result view section tab issues fixed
- **utils**: update print statement formatting in smart_filter_images function
- **example**: update VirtuGhan version in usage example to 0.6.0

## 0.6.0 (2025-01-12)

### Feat

- smart filters option

### Fix

- **example**: enable timeseries in VirtuGhan usage example
- **export**: fixes issue on export only

## 0.5.0 (2025-01-12)

### Feat

- **smartfilter**: added smartfilter on the api requests
- loader implemented in view modal of result
- loader on image list - result tab
- time series trend added to result view

### Fix

- export clear now clearing the band select button
- search layer not checked after search button click in second attempt after unchecking result layer
- view result active tab issue after close modal
- **stac**: make stac api url single and avoid repeatition

## 0.4.0 (2025-01-11)

### Feat

- add operation and timeseries parameters to get_tile function

### Fix

- **graph**: fixes trend on graph with order of the images
- **vcube**: change default operation to median and implement result aggregation with trend visualization
- **tile**: enhance image filtering logic in smart_filter_images function
- **tile**: handle empty results and improve error handling in TileProcessor
- **workflow**: remove 'main' branch from Docker build and publish triggers
- **get_tile**: update default operation to 'mean' and set timeseries default to False
- **latest**: added latest tile fetch for the on the fly computation
- **tile**: operation accross the time dimention
- update zoom level validation and enhance tile layer configurations

### Refactor

- simplify output directory assignment in extract_raw_bands_as_image function

## 0.3.4 (2025-01-10)

### Fix

- **zip**: don't zip by default and add argument to control the behaviour

## 0.3.3 (2025-01-10)

### Fix

- **zip**: storage issue , added zip compression

### Refactor

- **api**: rename extract_raw_bands endpoint to image-download and update related functions

## 0.3.2 (2025-01-10)

### Fix

- **extractband**: added extraction feature on the api and extract
- **example**: update execution time in usage example output

## 0.3.1 (2025-01-07)

### Fix

- **filter**: fixed bug on typo engine
- **example**: update VirtuGhan version to 0.3.0 and adjust execution counts in usage example

## 0.3.0 (2025-01-07)

### Feat

- **extract**: added data extraction method on the package

## 0.2.1 (2025-01-06)

### Fix

- **overlaps**: fixes bug on overlapping images occored due to two different satellite image capture

## 0.2.0 (2025-01-06)

### Feat

- add favicon to the index page

### Fix

- **largeimage**: fixed bug on large image processing range
- update start date for data processing in usage example

## 0.1.5 (2025-01-06)

### Fix

- **api**: fixes api bug on multiple request async
- previous images cleared from timeseries

## 0.1.4 (2025-01-05)

### Fix

- **mode**: disable mode in api param as well

## 0.1.3 (2025-01-05)

### Fix

- **imagetitle**: fixes bug on image title on giff
- **nodata**: fix bug on nodata pixels for the output

## 0.1.2 (2025-01-05)

### Fix

- **nodata**: fix bug on nodata pixels for the output

## 0.1.1 (2025-01-05)

### Fix

- **version**: increase limit of stac api search prevent 100

## 0.1.0 (2025-01-05)

### Feat

- **engine**: add option to run engine on parallel

## 0.0.3 (2025-01-05)

### Fix

- **mode**: remove mode to get rid of scipy for now
- icon click to button click on view and download result

### Refactor

- **toml**: formatting

## 0.0.2 (2025-01-05)
