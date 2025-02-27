# HOTWIRE:

# csv generator for generating robot TCP-toolpaths for foamcutting with hot wire cutters
# intended use is for tapered foam wings with sweep and dihedral
# csv input data can be gathererd from http://airfoiltools.com/


import numpy as np
from scipy.interpolate import interp1d
import matplotlib.pyplot as plt
import math
from matplotlib import cm
from numpy import sin, cos, pi
import shapely.geometry as shp


def point_distance(x1, x2, y1, y2):
    return np.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)


def vec_ang(v1, v2):
    if np.allclose(v1 / np.linalg.norm(v1), v2 / np.linalg.norm(v2)): return 0
    if np.allclose(v1 / np.linalg.norm(v1), -v2 / np.linalg.norm(v2)): return pi
    ang = np.arccos(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))
    return ang


def arc_length(f, a, b):
    npts = 100
    x = np.linspace(a, b, npts)
    y = f(x)
    arc = np.sqrt((x[1] - x[0]) ** 2 + (y[1] - y[0]) ** 2)
    for k in range(1, npts):
        arc = arc + np.sqrt((x[k] - x[k - 1]) ** 2 + (y[k] - y[k - 1]) ** 2)
    return arc


def Rz(a):
    return np.array([[cos(a), -sin(a), 0],
                     [sin(a), cos(a), 0],
                     [0, 0, 1]])


def segmenter(segs, profile_len, arc_len, interpol):
    print("\nsegmenting interpol function (profile_len = {}) at target segments: {}".format(profile_len, segs))

    segments = np.zeros([segs, 3])
    segments[0] = [0, 0, 0]
    for i in range(0, segs):
        overflower = 0
        x_min = segments[i][0]
        x_max = profile_len - 1e-6
        actions = ""
        if x_min > (profile_len - profile_len / segs):
            print("...profile fully segmented into segments: " + str(i))
            break

        while True:
            overflower += 1
            dist = point_distance(segments[i][0], x_max, interpol(segments[i][0]), interpol(x_max))
            # dist = arc_length(interpol, x_min, x_max)

            if abs(dist - arc_len) < 0.0001:
                if x_max > profile_len: x = profile_len
                segments[i + 1] = [x_max, interpol(x_max), 0]
                break

            if dist > arc_len:
                x_max = x_max - abs(x_max - x_min) / 2
                actions += "down "
            else:
                tx = x_max
                x_max = abs(x_max - x_min) / 2 + x_max
                x_min = tx
                actions += "up "

            if x_max > profile_len: raise Exception(
                "x_max > profile_len at i: {} \nx_min is {}, x_max is {}\nactions are: {}".format(i, x_min, x_max,
                                                                                                  actions))
            if x_max < x_min: raise Exception(
                "x_min < x_max at i: {} \nx_min is {}, x_max is {}".format(i, x_min, x_max))
            if overflower > 10000: raise Exception("Overflow!")

    # remove zeros
    for i in range(len(segments)):
        if (segments[i] == np.array([[0, 0, 0]])).all() and i != 0: return segments[:i]
    return segments


def plot_3d(s_segments, l_segments, us_segments, ul_segments, l_profile_len, wingspan, zoomout=False):
    fig = plt.figure()
    ax = plt.axes(projection='3d')

    XX1 = np.append(l_segments[:, 0], s_segments[:, 0])
    YY1 = np.append(l_segments[:, 1], s_segments[:, 1])
    ZZ1 = np.append(l_segments[:, 2], s_segments[:, 2])

    ax.plot_trisurf(XX1, YY1, ZZ1, linewidth=0.5, antialiased=True, shade=True, cmap=cm.coolwarm)

    XX2 = np.append(ul_segments[:, 0], us_segments[:, 0])
    YY2 = np.append(ul_segments[:, 1], us_segments[:, 1])
    ZZ2 = np.append(ul_segments[:, 2], us_segments[:, 2])
    ddd_plot = ax.plot_trisurf(XX2, YY2, ZZ2, linewidth=0.5, antialiased=True, shade=True, cmap=cm.coolwarm)

    if zoomout:
        ax.set_xlim3d(-50 - l_profile_len, 50 + l_profile_len)
        ax.set_ylim3d(-50 - l_profile_len, 50 + l_profile_len)
        ax.set_zlim3d(-50 - l_profile_len, 50 + l_profile_len)
    else:
        if wingspan > l_profile_len:
            l_profile_len = wingspan
        ax.set_xlim3d(0, -l_profile_len)
        ax.set_ylim3d(0, l_profile_len)
        ax.set_zlim3d(0, l_profile_len)

    ax.set_xlabel('X axis')
    ax.set_ylabel('Y axis')
    ax.set_zlabel('Z axis')
    plt.gca().set_aspect('auto', adjustable='box')
    # plt.show()
    # input("ddd_plot is {}".format(ddd_plot))
    return [(XX1, YY1, ZZ1), (XX2, YY2, ZZ2), (wingspan, l_profile_len)]


def data_refiner(datapath):
    data = np.genfromtxt(datapath, delimiter=",")

    # remove all nans and slice everyting else
    deleter = []
    for row, i in zip(data, range(len(data))):
        if np.isnan(row).any():
            deleter.append(i)

    for i in range(len(deleter)):
        if deleter[i + 1] - deleter[i] > 1:
            deleter = np.append(deleter[0:i + 1], range(deleter[i + 1], len(data)))
    data = np.delete(data, deleter, axis=0)
    return data[:, 0], data[:, 1]


def shorten_array(input_arr, target_length):
    """

    :param input_arr:
    :param target_length: has to be smaller than the length of the given array
    :type input_arr: List or Numpy Array
    :type target_length: int
    :return: Shortened array with "target_length" elements
    """

    assert len(input_arr) >= target_length

    array = np.array(input_arr)

    if len(input_arr) != target_length:
        diff = len(input_arr) - target_length
        for _ in range(diff):
            array = np.delete(array, np.random.randint(0, len(array)), axis=0)

    return array

def hotwire(big_data=None, small_data=None, distance=200, sweep=200, dihedral=115, twist=0, tool_diameter=1,
            diheral_angle=30,
            s_profile_len=100, l_profile_len=300, num_segs=250, retract_path_length=50, mirror=False, loadonly=True):
    """
    This function generates a tool path
    Input data consists of two NumPy arrays containing raw data from both CSV input files
    Input data (which represents a wing profile) should be points on a closed curve
    The closed curve can't be interpoloted using regular linear interpolation functions.
    Thus the input data is first divided into a top and a bottom line, then cast into two interpolation functions.
    Then the interpolated functions (2 times top and bottom equals 4 functions total) are divided into segments of equal arc length
    The arc lengths of the individual segments are proportioned according to the arc length of each interpolated curve
    After the segmentation process you should end up with an equal amount of segments on both top-pairs and bottom-pairs
    Vectors are traced between two segment pairs 
    Finally, a TCP Movement is calculated using the latter vector array
    
        -> this method ensures that leading edge and trailing edge of both pairs are connected
        -> the method has a shortcoming on highly irregular contours which cant be cast into a top and bottom function
        -> (i.e. slats, flaps or recurring slots for design purposes)
        -> potential future updates may consist of better interpolation allowing more complex contours

        :type num_segs: int
        :type big_data: list
        :type small_data: list
        :type distance: int
        :type sweep: int
        :type dihedral: int
        :type twist: int
        :type tool_diameter: int
        :type diheral_angle: int
        :type s_profile_len: int
        :type l_profile_len: int
        :type retract_path_length: int
        :type mirror: bool
        :type loadonly: bool
        :return:
    """

    num_segs = int(num_segs)

    big_x, big_y = data_refiner(big_data)
    small_x, small_y = data_refiner(small_data)

    # devide data into top and bottom: first find xmin and xmax
    big_xmin_index = np.where(big_x == np.amin(big_x))[0]
    big_xmax_index = np.where(big_x == np.amax(big_x))[0]
    small_xmin_index = np.where(small_x == np.amin(small_x))[0]
    small_xmax_index = np.where(small_x == np.amax(small_x))[0]

    print("indicies: {}, {}, {}, {}".format(big_xmin_index, big_xmax_index, small_xmin_index, small_xmax_index))
    over_big_x = big_x[big_xmax_index[0]: big_xmin_index[0] + 1]
    over_big_y = big_y[big_xmax_index[0]: big_xmin_index[0] + 1]
    under_big_x = big_x[big_xmin_index[0]: big_xmax_index[1] + 1]
    under_big_y = big_y[big_xmin_index[0]: big_xmax_index[1] + 1]

    over_small_x = small_x[small_xmax_index[0]: small_xmin_index[0] + 1]
    over_small_y = small_y[small_xmax_index[0]: small_xmin_index[0] + 1]
    under_small_x = small_x[small_xmin_index[0]: small_xmax_index[1] + 1]
    under_small_y = small_y[small_xmin_index[0]: small_xmax_index[1] + 1]

    # interpolate data
    over_big_interpol = interp1d(over_big_x, over_big_y, kind='linear')
    under_big_interpol = interp1d(under_big_x, under_big_y, kind='linear')

    over_small_interpol = interp1d(over_small_x, over_small_y, kind='linear')
    under_small_interpol = interp1d(under_small_x, under_small_y, kind='linear')

    # show data big_interpol small_interpol
    showdata = False
    if showdata:
        plt.plot(np.linspace(0, l_profile_len, 3000), over_big_interpol(np.linspace(0, l_profile_len, 3000)))
        plt.plot(np.linspace(0, l_profile_len, 3000), under_big_interpol(np.linspace(0, l_profile_len, 3000)))
        plt.grid("on")
        plt.plot(np.linspace(0, s_profile_len, 3000), over_small_interpol(np.linspace(0, s_profile_len, 3000)))
        plt.plot(np.linspace(0, s_profile_len, 3000), under_small_interpol(np.linspace(0, s_profile_len, 3000)))
        plt.plot(big_x, big_y, "ro")
        data_plot = plt.plot(small_x, small_y, "ro")
        plt.gca().set_aspect('equal', adjustable='box')
        plt.show()

    # calculate circumference and arc_len
    over_circumf_large = arc_length(over_big_interpol, 0, l_profile_len)
    under_circumf_large = arc_length(under_big_interpol, 0, l_profile_len)
    over_circumf_small = arc_length(over_small_interpol, 0, s_profile_len)
    under_circumf_small = arc_length(under_small_interpol, 0, s_profile_len)

    over_large_arc_len = over_circumf_large / num_segs
    under_large_arc_len = under_circumf_large / num_segs
    over_small_arc_len = over_circumf_small / num_segs
    under_small_arc_len = under_circumf_small / num_segs

    # Segmenting
    print("running segmenter")

    # small profile:
    over_s_segments = segmenter(num_segs, s_profile_len, over_small_arc_len, over_small_interpol)
    under_s_segments = segmenter(num_segs, s_profile_len, under_small_arc_len, under_small_interpol)

    # large profile
    over_l_segments = segmenter(num_segs, l_profile_len, over_large_arc_len, over_big_interpol)
    under_l_segments = segmenter(num_segs, l_profile_len, under_large_arc_len, under_big_interpol)

    # check if segments match up, if necessary: delete a random segment
    # All 4 arrays have to have the same amount of elements


    seg_amt_ols = len(over_l_segments)
    seg_amt_uls = len(under_l_segments)
    seg_amt_oss = len(over_s_segments)
    seg_amt_uss = len(under_s_segments)

    min_amt = min(seg_amt_uss, seg_amt_uls, seg_amt_ols, seg_amt_ols)

    over_l_segments = shorten_array(over_l_segments, min_amt)
    over_s_segments = shorten_array(over_s_segments, min_amt)
    under_l_segments = shorten_array(under_l_segments, min_amt)
    under_s_segments = shorten_array(under_s_segments, min_amt)

    print("ols contains {} segments, oss contains {} segments".format(len(over_l_segments), len(over_s_segments)))
    print("uls contains {} segments, uss contains {} segments".format(len(under_l_segments), len(under_s_segments)))

    # offset points radially from original curve by tool diameter
    plots = []
    shiny_outputs = []

    tr = tool_diameter / 2

    segments = np.array([over_l_segments, under_l_segments, over_s_segments, under_s_segments])
    old_shape = segments.shape
    segments = segments.reshape(segments.shape[0]*segments.shape[1], -1)

    shape = shp.Polygon(segments)
    offset_shape = shape.buffer(-tr, segments.shape[0])
    segments = np.array(shape.exterior)[0:-1, :]

    segments = segments.reshape(old_shape)

    offset_ols = segments[0]
    offset_uls = segments[1]
    offset_oss = segments[2]
    offset_uss = segments[3]

    # apply twist:
    twist *= pi / 180
    offset_oss = (np.dot(Rz(twist), offset_oss.T)).T
    offset_uss = (np.dot(Rz(twist), offset_uss.T)).T
    over_s_segments = (np.dot(Rz(twist), over_s_segments.T)).T
    under_s_segments = (np.dot(Rz(twist), under_s_segments.T)).T

    # Set wingspan, sweep and dihedral
    translatory = np.array([sweep, dihedral, -distance])
    over_s_segments += translatory
    offset_oss += translatory
    under_s_segments += translatory
    offset_uss += translatory

    # Generate plots
    print("generating plots")
    plt.grid("on")
    plt.plot(np.linspace(0, l_profile_len, 3000), over_big_interpol(np.linspace(0, l_profile_len, 3000)), "b")
    plt.plot(np.linspace(0, l_profile_len, 3000), under_big_interpol(np.linspace(0, l_profile_len, 3000)), "b")

    plt.plot(over_s_segments[:, 0], over_s_segments[:, 1], "r")
    plt.plot(under_s_segments[:, 0], under_s_segments[:, 1], "r")

    plt.plot(over_l_segments[:, 0], over_l_segments[:, 1], "r")
    plt.plot(under_l_segments[:, 0], under_l_segments[:, 1], "r")

    # add offset data:

    plt.plot(offset_ols[:, 0], offset_ols[:, 1], "g")
    plt.plot(offset_uls[:, 0], offset_uls[:, 1], "g")
    plt.plot(offset_oss[:, 0], offset_oss[:, 1], "g")
    post_seg_plot = plt.plot(offset_uss[:, 0], offset_uss[:, 1], "g")

    plt.gca().set_aspect('equal', adjustable='box')

    # Clean up data
    for dataset in offset_ols, offset_oss, offset_uls, offset_uss:
        dataset[:, 0] = dataset[:, 0] - l_profile_len
        dataset = dataset[1:]

    # Mirror data
    if mirror:
        print("...mirroring")
        mirr = ["right", "left"]
        save_offset_ols = np.copy(offset_ols)
        save_offset_uls = np.copy(offset_uls)
        save_offset_oss = np.copy(offset_oss)
        save_offset_uss = np.copy(offset_uss)

    else:
        mirr = [""]

    for m in mirr:
        if m == "left":
            # load save
            offset_ols = save_offset_ols
            offset_uls = save_offset_uls
            offset_oss = save_offset_oss
            offset_uss = save_offset_uss

            for off in offset_ols, offset_uls, offset_oss, offset_uss:
                off[:, 2] *= -1

        # 3D Plot
        plotprerot = False
        if plotprerot:
            print("\nshowing 3d plot pre rotation:")
            plot_3d(offset_oss, offset_ols, offset_uss, offset_uls, l_profile_len, distance)

        # rotate points
        a = (90 - diheral_angle) * np.pi / 180
        if m == "left": a *= -1
        Rx_alph = np.array([[1, 0, 0],
                            [0, np.cos(a), -np.sin(a)],
                            [0, np.sin(a), np.cos(a)]])

        for seg, i in zip(offset_ols, range(len(offset_ols))): offset_ols[i] = np.dot(Rx_alph, seg)
        for seg, i in zip(offset_uls, range(len(offset_uls))): offset_uls[i] = np.dot(Rx_alph, seg)

        for seg, i in zip(offset_oss, range(len(offset_oss))): offset_oss[i] = np.dot(Rx_alph, seg)
        for seg, i in zip(offset_uss, range(len(offset_uss))): offset_uss[i] = np.dot(Rx_alph, seg)

        # 3D Plot
        plotpostrot = True
        if plotpostrot:
            print("\nshowing 3d plot post rotation:")
            plots.append(plot_3d(offset_oss, offset_ols, offset_uss, offset_uls, l_profile_len, distance))

        # Add retract path
        rl = retract_path_length
        offset_ols = np.append(offset_ols, offset_ols[-1] + np.array([[rl, 0, 0]]), axis=0)
        offset_uls = np.append(offset_uls, offset_uls[-1] + np.array([[rl, 0, 0]]), axis=0)
        offset_oss = np.append(offset_oss, offset_oss[-1] + np.array([[rl, 0, 0]]), axis=0)
        offset_uss = np.append(offset_uss, offset_uss[-1] + np.array([[rl, 0, 0]]), axis=0)

        # Tracing vectors from large_segs to small_segs
        over_vec_space = np.zeros([len(offset_oss), 3])
        for i in range(len(over_vec_space)):
            u = offset_oss[i][0] - offset_ols[i][0]
            v = offset_oss[i][1] - offset_ols[i][1]
            w = offset_oss[i][2] - offset_ols[i][2]
            over_vec_space[i] = [u, v, w]

        under_vec_space = np.zeros([len(offset_uss), 3])
        for i in range(len(under_vec_space)):
            u = offset_uss[i][0] - offset_uls[i][0]
            v = offset_uss[i][1] - offset_uls[i][1]
            w = offset_uss[i][2] - offset_uls[i][2]
            under_vec_space[i] = [u, v, w]

        # Calculate TCP movment through vector space
        e1 = np.array([1, 0, 0])
        e2 = np.array([0, 1, 0])
        e3 = np.array([0, 0, 1])

        def vec2abc(v):
            vproj = v * (e1 + e2)
            c = pi

            if v[2] > 0:
                sign = -1
            else:
                sign = 1
            b = sign * vec_ang(v, vproj)

            if v[1] > 0:
                sign = 1
            else:
                sign = -1
            a = sign * vec_ang(e1, vproj)

            return [a, b, c]

        X, Y, Z = [], [], []
        A, B, C = [], [], []
        for i in range(len(offset_ols)):
            X.append(offset_ols[-i][0])
            Y.append(offset_ols[-i][1])
            Z.append(offset_ols[-i][2])

            A.append(vec2abc(over_vec_space[-i])[0])
            B.append(vec2abc(over_vec_space[-i])[1])
            C.append(vec2abc(over_vec_space[-i])[2])

        for i in range(len(offset_uls)):
            X.append(offset_uls[i][0])
            Y.append(offset_uls[i][1])
            Z.append(offset_uls[i][2])

            A.append(vec2abc(under_vec_space[i])[0])
            B.append(vec2abc(under_vec_space[i])[1])
            C.append(vec2abc(under_vec_space[i])[2])

        # X = np.array(X) - l_profile_len
        """for dataset in offset_ols, offset_oss, offset_uls, offset_uss:
            dataset[:,0] = dataset[:,0] - l_profile_len
            dataset = dataset[1:]"""

        # Save to document:
        output = np.transpose(np.array([X, Y, Z, A, B, C]))
        output = output[1:]
        print(len(X))
        print(len(Y))
        print(len(Z))
        print(len(A))
        print(len(B))
        print(len(C))

        shiny_output = np.append(np.array([["TCP coordinates + TCP rotation", "", "", "", "", ""]]), output, axis=0)

        shiny_output = np.append(shiny_output,
                                 np.array([["Large segments xyz +small segments xyz", "", "", "", "", ""]]), axis=0)
        shiny_output = np.append(shiny_output, np.append(offset_ols[::-1], offset_oss[::-1], axis=1), axis=0)
        shiny_output = np.append(shiny_output, np.append(offset_uls, offset_uss, axis=1), axis=0)

        shiny_outputs.append(shiny_output)

        # np.savetxt("outupt_{}.csv".format(m), shiny_output, delimiter=";", fmt="%s")
        # print("\nSaved successfully to file named {}!".format("outupt_{}.csv".format(m)))

    return post_seg_plot[0], plots, shiny_outputs
