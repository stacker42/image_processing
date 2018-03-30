import matplotlib

matplotlib.use('Agg')
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib import figure
import io


def image_plot(x, y, x_label, y_label, limits, colours, shapes):
    """
    Generate an image (in memory) of a lightcurve for a specific star
    :param star: The star we want to make a plot of
    :param filters: The filters we want to include in the plot
    :return: The image
    """
    buff = io.BytesIO()
    fig = figure.Figure()
    canvas = FigureCanvasAgg(fig)

    i = 0
    axes = fig.add_subplot(211)
    while i < len(x):
        axes.scatter(x[i]['dates'], y[i]['magnitudes'], marker=shapes[y[i]['filter']], c=colours[y[i]['filter']])
        i += 1

    if limits[0] is not None:
        axes.set_xlim(left=float(limits[0]))
    if limits[1] is not None:
        axes.set_xlim(right=float(limits[1]))
    if limits[2] is not None:
        axes.set_ylim(bottom=float(limits[2]))
    if limits[3] is not None:
        axes.set_ylim(top=float(limits[3]))

    axes.set_ylabel(ylabel=y_label)
    axes.set_xlabel(xlabel=x_label)

    axes.invert_yaxis()

    fig.tight_layout()
    fig.set_size_inches(7, 8)

    fig.savefig(buff, format='png', bbox_inches='tight', dpi=600)

    buff.seek(0)

    return buff
