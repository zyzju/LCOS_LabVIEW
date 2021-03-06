"""
This modeul conatins functions to compute the multispot LCOS pattern.

Unless specified otherwise, coordinates are in LCOS pixel units.
"""


import numpy as np


LOG_FILE = 'C:/Data/Antonio/software/LCOS/python_out.txt'

# LCOS constants
LCOS_X_SIZE, LCOS_Y_SIZE, LCOS_PIX_SIZE = 800, 600, 20e-6

# Allocate the (x, y) grid once when the module is imported
YL, XL = np.mgrid[:LCOS_Y_SIZE, :LCOS_X_SIZE]


def fprint(s):
    with open(LOG_FILE, "a") as myfile:
        myfile.write(str(s)+'\n')


def fprint_kw(**kwargs):
    with open(LOG_FILE, "a") as myfile:
        s = ', '.join([k +'='+str(v) for k,v in kwargs.items()])
        myfile.write(s+'\n')


def black_pattern(dtype=np.uint8):
    return np.zeros((LCOS_Y_SIZE, LCOS_X_SIZE), dtype=dtype)


def phase_spherical(r, f, wavelen=532e-9):
    """Phase profile (in pi units) at distance r (x,y) from spot center
    for a spherical wave converging at a distance f from the screen.
    Inputs in SI units. The formula is exact, not approximated."""
    return -(2/wavelen) * (np.sqrt(r**2 + f**2) - f)


def get_steer_pattern(lw, vmax=255, horizontal=True, debug=False):
    """Horizontal or vertical pattern for beam steering.

    Arguments:
        lw (uint): line-width in LCOS pixels for the steering pattern
        vmax (int, 0..255): max value for the steering pattern
        horizontal (bool): if True draw horizontal line, else vertical
    """
    a = black_pattern()
    if vmax > 0:
        if debug:
            fprint_kw(lw_pos_assert=(lw > 0), horizontal=horizontal)
            assert lw > 0
        row_wise_a = a
        if not horizontal:
            row_wise_a = a.T
        for i in range(0, row_wise_a.shape[0], 2*lw):
            row_wise_a[i:i+lw] = vmax
    return a

def spotmap_func(x, y, pitch_xy, nspots_xy):
    """Return the spot number containing the input point(s).

    Arguments:
        x, y (arrays of floats): coordinates of the input points
            to be labeled with a spot number. The coordinates needs to be
            in the LCOS frame of reference with origin in the LCOS center.
        pitch_xy (tuple of 2 floats): X and Y pattern pitch in LCOS pixels.
        nspots_xy (tuple of 2 ints): number of spots in X and Y direction.

    Returns:
        Return an array with same shape as `x` (or `y`) containing an integer
        label (the spot number) for each input point. If no spot contains
        a given point the value will be NaN.
    """
    assert x.shape == y.shape
    spotnum = [0, 0]
    for i, (v, pitch, nspots) in enumerate(zip((x, y), pitch_xy, nspots_xy)):
        offset = 0 if (nspots % 2) == 0 else 0.5
        spotnum[i] = np.floor(v / pitch + offset)
        smin, smax = -(nspots // 2), (nspots // 2) + nspots % 2 - 1
        spotnum[i][(spotnum[i] < smin) + (spotnum[i] > smax)] = np.nan
    Z = spotnum[0] + spotnum[1] * nspots_xy[0]
    Z -= np.nanmin(Z)
    return Z


def pitch_from_centers(X, Y):
    """Estimate spot pitch in X and Y direction from spot centers (X, Y).
    """
    assert X.shape == Y.shape
    assert X.size > 1
    nspots_y, nspots_x = X.shape
    if nspots_x > 1 and nspots_y == 1:
        pitch_x = pitch_y = np.mean(np.diff(X, axis=1))
    elif nspots_y > 1 and nspots_x == 1:
        pitch_x = pitch_y = np.mean(np.diff(Y, axis=0))
    else:
        # both nspots_x and nspots_y are > 1
        pitch_x = np.mean(np.diff(X, axis=1))
        pitch_y = np.mean(np.diff(Y, axis=0))
    return pitch_x, pitch_y


def get_spot_regions(nspots_x, nspots_y, pitch_x, pitch_y,
                     center_x=0, center_y=0, rotation=0):
    """Compute rectangular regions for each spot.

    For details of the algorithm see notebook:

    - Pattern Roto-Translation Documentation.ipynb

    Arguments:
        nspots_x, nspots_y (ints): number of spots in the X and Y direction.
        pitch_x, pitch_y (floats): spot pitch in X and Y direction.
        center_x, center_y (floats): coordinate of the pattern center.
        rotation (float): pattern rotation angle in degree.

    Returns:
        2D array of labels (ints) on the LCOS frame of reference. Spots are
        numbered starting from 0 and going thorugh columns first.
    """
    # NOTE: XL, YL are coordinates of LCOS pixels with origin in the corner.
    #       center_x, center_y are the coordinates of the pattern center with
    #       origin in the LCOS center.
    XLtr, YLtr = rotate((XL - LCOS_X_SIZE // 2 - center_x),
                        (YL - LCOS_Y_SIZE // 2 - center_y), angle=-rotation)
    spot_regions = spotmap_func(XLtr, YLtr, (pitch_x, pitch_y),
                                (nspots_x, nspots_y))
    return spot_regions


def get_spot_regionsC(X, Y, pitch_x=None, pitch_y=None,
                      center_x=None, center_y=None, rotation=0):
    """Compute rectangular regions for each spot.

    This version computes spot regions boundaries C, and then a 2D array
    of labels so the output is compatible (but not identical) with
    :func:`get_spot_regions`.

    Returns:
        2D array of labels (ints) on the LCOS frame of reference. Spots are
        numbered starting from 0 and going thorugh columns first.
    """
    assert X.shape == Y.shape
    Y_dim, X_dim = X.shape
    alpha = 0.5

    xpitch, ypitch = pitch_from_centers(X, Y)

    X_sep = (np.diff(X, axis=1)/2. + X[:,:-1])  # separators between spots
    # For each row (Y_dim)
    Xstart = np.array([(xl[0]-alpha*xpitch)-1 for xl in X]).reshape(Y_dim,1)
    Xend = np.array([(xl[-1]+alpha*xpitch)+1 for xl in X]).reshape(Y_dim,1)
    X_R = np.concatenate((Xstart,X_sep,Xend), axis=1)

    Y_sep = (np.diff(Y, axis=0)/2. + Y[:-1,:])  # separators between spots
    # For each col (X_dim)
    Ystart = np.array([(yl[0]-alpha*ypitch)-1 for yl in Y.T]).reshape(1,X_dim)
    Yend = np.array([(yl[-1]+alpha*ypitch)+1 for yl in Y.T]).reshape(1,X_dim)
    Y_R = np.concatenate((Ystart,Y_sep,Yend), axis=0)

    # C contains the limits (4 values) for each spot (one row per spot)
    C = np.zeros((Y_dim, X_dim, 4), dtype=np.int64)
    C[:,:,0] = np.ceil(X_R[:,:-1])  # xmin
    C[:,:,1] = np.floor(X_R[:,1:])  # xmax
    C[:,:,2] = np.ceil(Y_R[:-1,:])  # ymin
    C[:,:,3] = np.floor(Y_R[1:,:])  # ymax

    spot_regions = black_pattern(float) * np.nan
    ispot = 0
    for row in C:
        for xmin, xmax, ymin, ymax in row:
            spot_regions[ymin: ymax + 1, xmin: xmax + 1] = ispot
            ispot += 1
    return spot_regions


def get_spot_limits(X, Y, debug=False):
    """
    From an array of X, Y spot positions compute the boundaries for each spot.

    Returns:
        An array of shape (Y_dim, X_dim, 4), where for each spot (x, y)
        there are 4 values representing the spot boundaries in the following
        order: (xmin, xmax, ymin, ymax).
    """
    if debug:
        fprint_kw(X_Y_shape_assert=(X.shape == Y.shape))
        assert X.shape == Y.shape
    Y_dim, X_dim = X.shape
    alpha = 0.5

    ## Assumes at least one dimension > 1
    xpitch = np.mean(np.diff(X,axis=1))
    if Y_dim == 1:
        ypitch = xpitch # avoids Warning
    else:
        ypitch = np.mean(np.diff(Y,axis=0))
    if X_dim == 1: xpitch = ypitch
    if Y_dim == 1: ypitch = xpitch
    if debug:
        condition = (not np.isnan(xpitch)) and (not np.isnan(ypitch))
        fprint_kw(x_y_pitch_nan_assert=condition)
        assert condition

    X_sep = (np.diff(X, axis=1)/2. + X[:,:-1])  # separators between spots
    # For each row (Y_dim)
    Xstart = np.array([(xl[0]-alpha*xpitch)-1 for xl in X]).reshape(Y_dim,1)
    Xend = np.array([(xl[-1]+alpha*xpitch)+1 for xl in X]).reshape(Y_dim,1)
    X_R = np.concatenate((Xstart,X_sep,Xend), axis=1)

    Y_sep = (np.diff(Y, axis=0)/2. + Y[:-1,:])  # separators between spots
    # For each col (X_dim)
    Ystart = np.array([(yl[0]-alpha*ypitch)-1 for yl in Y.T]).reshape(1,X_dim)
    Yend = np.array([(yl[-1]+alpha*ypitch)+1 for yl in Y.T]).reshape(1,X_dim)
    Y_R = np.concatenate((Ystart,Y_sep,Yend), axis=0)

    # C contains the limits (4 values) for each spot (one row per spot)
    C = np.zeros((Y_dim, X_dim, 4), dtype=np.int64)
    C[:,:,0] = np.ceil(X_R[:,:-1])  # xmin
    C[:,:,1] = np.floor(X_R[:,1:])  # xmax
    C[:,:,2] = np.ceil(Y_R[:-1,:])  # ymin
    C[:,:,3] = np.floor(Y_R[1:,:])  # ymax
    return C


def single_spot_pattern(xm, ym, mask=None, a=None, f=30e-3, wavelen=532e-9,
                        phase_max=0):
    """Single spot lens and linear steering phase pattern (1 = pi).

    Arguments:
        xm, ym (floats): coordinates of the spot center in LCOS pixel units.
        mask (2D bool array): mask selecting the extension of the spot. The
            mask is usually True on a rectangular region around the spot center.
        a (2D array): an optional 2D array in which the pattern is written.
            Only the region defined by `mask` will be modified.
        f (float): focal length of the lens created on the phase pattern
            and used to focus a plane wave into a spot.
        wavelen (float): wavelength of the input laser.
        phase_max (float): a constant phase to add to the spherical phase
            of the spot. Since the spherical phase is 0 at its maximum
            (i.e. at the center xm, ym), the value `phase_max` is the max

    Returns:
        2D array containing a single spot. If `a` is passed it is modified
        in-place adding a single-spot pattern in the region defined by mask.
    """
    if a is None:
        a = black_pattern(float)
    if mask is None:
        mask = np.ones(a.shape, dtype=bool)
    radius = lambda x, y: np.sqrt(x**2 + y**2)
    R = radius((XL[mask] - xm)*LCOS_PIX_SIZE, (YL[mask] - ym)*LCOS_PIX_SIZE)
    a[mask] = phase_max + phase_spherical(R, f=f, wavelen=wavelen)
    return a


def multispot_pattern(Xm, Ym, labels, phase_max, f=30e-3, wavelen=532e-9,
            phase_factor=1, phase_wrap_pos=False, phase_wrap_neg=True,
            dtype=np.uint8, debug=False):
    """Pattern for spots centered in X,Y and rectangular limits defined in C.

    Arguments:
        Xm, Ym (2D arrays): coordinates of spot centers with respect to the
            LCOS center. The Xm and Ym shape (array's rows x cols) should
            be the same as the spot spot grid shape (pattern's rows x cols).
        labels (2D array): array of spot labels (ints) starting from 0.
            Defines rectangular regions for each spot on the LCOS image.
        phase_max (float): constant phase added to the pattern (in pi units).
            See :func:`single_spot_pattern` for details.
        f (float): focal length of the lens created on the phase pattern
            and used to focus a plane wave into a spot.
        wavelen (float): wavelength of the input laser.
        phase_factor (uint8): the 8-bit value [0..255] corresponding to pi
        phase_wrap_neg (bool): if True wraps all the negative-phase values into
            [0..phase_wrap_max]. phase_wrap_max is 2 when `phase_max` <= 2,
            otherwise is the smallest multiple of 2 contained in `phase_max`.
            When False, the negative phase values are set ot 0.
        phase_wrap_pos (bool): if True, wrap the positive phase values into
            [0..phase_wrap_max]. phase_wrap_max is 2 when `phase_max` <= 2,
            otherwise is the smallest multiple of 2 contained in `phase_max`.
        dtype (numpy.dtype): data type to use in the returned array.
            Default uint8.
        debug (bool): if True prints debugging info into the log file.

    Returns:
        A 2D array containing phase pattern image for the defined spots.
    """
    X = Xm + LCOS_X_SIZE // 2
    Y = Ym + LCOS_Y_SIZE // 2

    a = black_pattern(float)
    for ispot, (xm, ym) in enumerate(zip(X.ravel(), Y.ravel())):
        mask = labels == ispot
        single_spot_pattern(xm, ym, mask=mask, a=a, phase_max=phase_max,
                            f=f, wavelen=wavelen)

    if phase_wrap_neg or phase_wrap_pos:
        # smallest multiple of 2 contained in phase_max
        phase_wrap_max = 2 if phase_max <= 2 else (phase_max // 2) * 2

    if phase_wrap_pos:
        pos_phase = a > 0
        # wrap phase between 0 and phase_wrap_max (in pi units)
        a[pos_phase] = a[pos_phase] % phase_wrap_max

    neg_phase = a < 0
    if phase_wrap_neg:
        # wrap phase between 0 and phase_wrap_max (in pi units)
        a[neg_phase] = a[neg_phase] % phase_wrap_max
    else:
        a[neg_phase] = 0

    a *= phase_factor
    return a.round().astype(dtype)


def multispot_patternC(X, Y, C, phase_max, f=30e-3, wavelen=532e-9,
            phase_factor=1, phase_wrap_pos=False, phase_wrap_neg=True,
            dtype=np.uint8, debug=False):
    """Pattern for spots centered in X,Y and rectangular limits defined in C.

    Arguments:
        X, Y (2d arrays): center positions of the spots
        C (3d array): for each spot has 4 values (xmin, xmax, ymin, ymax)
            that defines the spot boundaries
        phase_max (float): constant phase added to the pattern (in pi units).
            See :func:`single_spot_pattern` for details.
        f (float): focal length of the lens created on the phase pattern
            and used to focus a plane wave into a spot.
        wavelen (float): wavelength of the input laser.
        phase_factor (uint8): the 8-bit value [0..255] corresponding to pi
        phase_wrap_neg (bool): if True wraps all the negative-phase values into
            [0..phase_wrap_max]. phase_wrap_max is 2 when `phase_max` <= 2,
            otherwise is the smallest multiple of 2 contained in `phase_max`.
            When False, the negative phase values are set ot 0.
        phase_wrap_pos (bool): if True, wrap the positive phase values into
            [0..phase_wrap_max]. phase_wrap_max is 2 when `phase_max` <= 2,
            otherwise is the smallest multiple of 2 contained in `phase_max`.
        dtype (numpy.dtype): data type to use in the returned array.
            Default uint8.
        debug (bool): if True prints debugging info into the log file.

    Returns:
        A 2D array containing phase pattern image for the defined spots.
    """
    a = black_pattern(float)

    for iy in range(X.shape[0]):
        for ix in range(X.shape[1]):
            xm, ym = X[iy, ix], Y[iy, ix]
            xmin, xmax, ymin, ymax = C[iy, ix]
            mask = (XL >= xmin) * (XL <= xmax) * (YL >= ymin) * (YL <= ymax)
            single_spot_pattern(xm, ym, mask=mask, a=a, phase_max=phase_max,
                                f=f, wavelen=wavelen)

    if phase_wrap_neg or phase_wrap_pos:
        # smallest multiple of 2 contained in phase_max
        phase_wrap_max = 2 if phase_max <= 2 else (phase_max // 2) * 2

    if phase_wrap_pos:
        pos_phase = a > 0
        # wrap phase between 0 and phase_wrap_max (in pi units)
        a[pos_phase] = a[pos_phase] % phase_wrap_max

    neg_phase = a < 0
    if phase_wrap_neg:
        # wrap phase between 0 and phase_wrap_max (in pi units)
        a[neg_phase] = a[neg_phase] % phase_wrap_max
    else:
        a[neg_phase] = 0

    a *= phase_factor
    return a.round().astype(dtype)


def get_outer_mask(C, pad=0):
    """Return a mask that selects outside the spot pattern.

    Arguments:
        pad (int): an additional padding in number of LCOS pixels to be
            added around the spot pattern.

    Returns:
        2D boolean array defining the region outside the spot pattern.
    """
    mask = np.ones(XL.shape, dtype=bool)
    for row in C:
        for xmin, xmax, ymin, ymax in row:
            mask[ymin - pad: ymax + 1 + pad, xmin - pad: xmax + 1 + pad] = False
    return mask


def phase_patternC(Xm, Ym, lens_params, steer_params, pad=2, ref_spot=4,
                  ref_spot_dark=False, dark_all=False, nospot=False,
                  debug=False):
    """Return the pattern with the multi-spot lenses and the beam steering.

    Arguments:
        pad (uint): # pixels of zero-padding around the lens pattern before
            the steering pattern starts.
        ref_spot (int): index of the spot considered as reference (e.g. center).
        ref_spot_dark (bool): if True darken the reference spot.
        dark_all (bool): if True return an array of zeros.
        nospot (bool): if True return only the steering pattern with no spots.
        debug (bool): if True prints debugging info into the log file.

    Returns:
        A 2D array containing the complete phase pattern image with both spots
        and beam steering pattern.
    """
    steer_params.update(debug=debug)
    lens_params.update(debug=debug)
    if dark_all:
        return black_pattern()
    if nospot:
        return get_steer_pattern(**steer_params)
    Xm = Xm.copy() + LCOS_X_SIZE/2.
    Ym = Ym.copy() + LCOS_Y_SIZE/2.
    XM, YM = np.atleast_2d(Xm), np.atleast_2d(Ym)
    if debug:
        fprint_kw(XM_YM_shape_assert=(len(XM.shape) == len(YM.shape) == 2))
        assert len(XM.shape) == len(YM.shape) == 2

    C = get_spot_limits(XM, YM, debug=debug)
    a = multispot_pattern(XM, YM, C, dtype=np.uint8, **lens_params)

    if ref_spot_dark:
        if ref_spot >= 0 and ref_spot < XM.size:
            nrows, ncols = XM.shape
            rspot_y = ref_spot // ncols
            rspot_x = ref_spot % ncols
            xmin, xmax, ymin, ymax = C[rspot_y, rspot_x]
            a[ymin:ymax + 1, xmin:xmax + 1] = 0
        else:
            print('WARNING: ref_spot out of range: %d' % ref_spot)
    if steer_params['vmax'] > 0:
        steer_img = get_steer_pattern(**steer_params)
        mask = get_outer_mask(C, pad=pad)
        a[mask] = steer_img[mask]
    return a


def phase_pattern(Xm, Ym, lens_params, steer_params, sparams=None, pad=2,
                  ref_spot=4,
                  ref_spot_dark=False, dark_all=False, nospot=False,
                  debug=False):
    """Return the pattern with the multi-spot lenses and the beam steering.

    Arguments:
        Xm, Ym (2D arrays): coordinates of spot centers with respect to the
            LCOS center. The Xm and Ym shape (array's rows x cols) should
            be the same as the spot spot grid shape (pattern's rows x cols).
        lens_params (dict): parameters for the multispot pattern.
        steer_params (dict): parameters for the beam steering pattern.
        pad (uint): # pixels of zero-padding around the lens pattern before
            the steering pattern starts.
        ref_spot (int): index of the spot considered as reference (e.g. center).
        ref_spot_dark (bool): if True darken the reference spot.
        dark_all (bool): if True return an array of zeros.
        nospot (bool): if True return only the steering pattern with no spots.
        debug (bool): if True prints debugging info into the log file.

    Returns:
        A 2D array containing the complete phase pattern image with both spots
        and beam steering pattern.
    """
    steer_params.update(debug=debug)
    lens_params.update(debug=debug)
    if dark_all:
        return black_pattern()
    if nospot:
        return get_steer_pattern(**steer_params)
    XM, YM = np.atleast_2d(Xm), np.atleast_2d(Ym)
    assert len(XM.shape) == len(YM.shape) == 2

    if sparams is None:
        nspots_x, nspots_y = XM.shape
        pitch_x, pitch_y = pitch_from_centers(XM, YM)
        sparams = dict(nspots_x=nspots_x, nspots_y=nspots_y,
                       pitch_x=pitch_x, pitch_y=pitch_y,
                       center_x=XM.ravel().mean(), center_y=YM.ravel().mean())
    spot_regions = get_spot_regions(**sparams)

    if ref_spot_dark:
        if ref_spot >= 0 and ref_spot < XM.size:
            spot_regions[spot_regions == ref_spot] = np.nan
        else:
            print('WARNING: ref_spot out of range: %d' % ref_spot)

    a = multispot_pattern(XM, YM, spot_regions, dtype=np.uint8, **lens_params)

    if steer_params['vmax'] > 0:
        # NOTE: pad is ignored here
        steer_img = get_steer_pattern(**steer_params)
        mask = np.isnan(spot_regions)
        a[mask] = steer_img[mask]
    return a


def spot_coord_grid(nspots_x, nspots_y, pitch_x=25, pitch_y=25,
                    center_x=0, center_y=0, rotation=0):
    """Returns the coordinates of spots arranged on a rectangular grid.

    Arguments:
        nspots_x, nspots_y (ints): number of spots in the X and Y direction.
        pitch_x, pitch_y (floats): spot pitch in X and Y direction.
        center_x, center_y (floats): coordinate of the pattern center.
        rotation (float): pattern rotation angle in degree.

    Returns:
        A tuple (X, Y) of two 2D arrays containing the grid of spot centers
        coordinates with respect to the LCOS center and in LCOS pixel units.
        These arrays can be directly passed to :func:`phase_pattern` to
        generate a pattern of spots.
    """
    xp = (np.arange(0, nspots_x, dtype=float) - (nspots_x-1)/2) * pitch_x
    yp = (np.arange(0, nspots_y, dtype=float) - (nspots_y-1)/2) * pitch_y
    Xp, Yp = np.meshgrid(xp, yp)  # spot centers in pattern space

    # Roto-translation to go to LCOS space
    Xm, Ym = rotate(Xp, Yp, rotation)
    Xm += center_x
    Ym += center_y
    return Xm, Ym


def rotate(x, y, angle):
    """Rotate the point (x, y) (or array of points) with respect to the origin.

    Arguments:
        x, y (flaots or arrays): input coordinates to be transformed.
        angle (float): rotation angle in degrees. When the Y axis points
            up and the X axis points right, a positive angle result in
            a counter-clock-wise rotation.

    Returns:
        New coordinates or the rotated point.
    """
    if angle == 0:
        return x, y
    shape = x.shape
    assert shape == y.shape
    x_ = x.ravel()
    y_ = y.ravel()
    theta = angle * np.pi / 180
    rot_matrix = np.array([[np.cos(theta), -np.sin(theta)],
                           [np.sin(theta), np.cos(theta)]])
    v = np.vstack([x_, y_])
    xr, yr = rot_matrix @ v
    return xr.reshape(shape), yr.reshape(shape)


def get_test_pattern():
    a = np.arange(LCOS_Y_SIZE * LCOS_X_SIZE, dtype=float)
    a *= (255 / a.max())
    a[:256] = np.arange(256)
    a[LCOS_X_SIZE:LCOS_X_SIZE + 256] = np.arange(256)[::-1]
    return a.astype('uint8').reshape(LCOS_Y_SIZE, LCOS_X_SIZE)


def spot_coord_test():
    step = 50
    Xm = np.arange(-200, 200, step, dtype=float)
    Ym = 10 * np.cos(Xm * 2*np.pi / (4*step))
    return Xm, Ym


def sanitize_spot_coord(Xm, Ym):
    if len(Xm) == 0 or len(Ym) == 0:
        print('WARNING: At lest one spot coordinate is empy.')
        return spot_coord_test()
    elif len(Xm) != len(Ym):
        print('WARNING: X and Y spot coordinates have different sizes.')
        return spot_coord_test()

    Xm = np.array(Xm)
    Ym = np.array(Ym)
    return Xm, Ym


def pattern_from_dict(ncols, nrows, rotation, spotsize, pitch_x, pitch_y,
                 center_x, center_y, wavelen, steer_lw, steer_vmax,
                 ref_spot, focal, phase_max, phase_factor, steer_pad,
                 Xm, Ym, phase_wrap_pos, phase_wrap_neg, steer_horiz,
                 test_pattern, nospot, grid, dark_all, ref_spot_dark, debug):
    if test_pattern:
        return get_test_pattern()

    sparams = None
    if grid:
        sparams = dict(nspots_x=ncols, nspots_y=nrows,
                       rotation=rotation, pitch_x=pitch_x, pitch_y=pitch_y,
                       center_x=center_x, center_y=center_y)
        Xm, Ym = spot_coord_grid(**sparams)
    else:
        Xm, Ym = sanitize_spot_coord(Xm, Ym)

    lens_params = dict(wavelen=wavelen, f=focal, phase_max=phase_max,
                       phase_factor=phase_factor,
                       phase_wrap_pos=phase_wrap_pos,
                       phase_wrap_neg=phase_wrap_neg)

    steer_params = dict(vmax=steer_vmax, lw=steer_lw,
                        horizontal=steer_horiz)
    a = phase_pattern(Xm, Ym, lens_params, steer_params, sparams=sparams,
                      pad=steer_pad,
                      ref_spot_dark=ref_spot_dark, ref_spot=ref_spot,
                      dark_all=dark_all, nospot=nospot, debug=debug)
    return a


if __name__ == "__main__":
    pass
    # lens_params = dict(wavelen=532e-9, f=32e-3, phase_max=4, phase_factor=64,
    #                    phase_wrap_pos=False, phase_wrap_neg=True)
    # steer_params = dict(vmax=120, lw=180, horizontal=False)
    #
    # Xm = np.array([  23.87  ,   46.99  ,   70.1875,   93.4175,  116.6275,
    #                139.6825,  162.715 ,  185.765 ])
    # Ym = np.array([ 15.5825,  15.56  ,  15.5875,  15.595 ,  15.5225,  15.545 ,
    #                15.5125,  15.47  ])
    #
    # a = phase_pattern(Xm,Ym, lens_params, steer_params, pad=2, ref_spot_dark=False)
