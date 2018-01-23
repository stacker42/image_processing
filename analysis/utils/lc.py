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

    axes = []
    i = 0
    while i < len(x):
        axes.append(fig.add_subplot(211))
        axes[i].scatter(x[i]['dates'], y[i]['magnitudes'])
        i += 1

    fig.tight_layout()
    fig.set_size_inches(7, 8)

    fig.savefig(buff, format='png', bbox_inches='tight', dpi=600)

    buff.seek(0)

    return buff