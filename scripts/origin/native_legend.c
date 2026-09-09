#include <Origin.h>

int rdop_native_legend_format(string label_format)
{
    GraphLayer layer = Project.ActiveLayer();
    return layer && legend_update(layer, ALM_CUSTOM, true, true, label_format);
}

// Use Origin's legend operations to select/order entries without hiding plots.
int rdop_native_legend(string plot_indices)
{
    GraphLayer layer = Project.ActiveLayer();
    if (!layer)
        return 0;
    if (!legend_update(layer, ALM_LONGNAME, true, true))
        return 0;
    int count = layer.DataPlots.Count();
    for (int index = 0; index < count; index++)
        legend_delete_plot(layer, index);
    for (int item = 0; ; item++)
    {
        string token = plot_indices.GetToken(item, ',');
        if (token.IsEmpty())
            break;
        int plot = atoi(token) - 1;
        if (plot < 0 || plot >= count || !legend_append_plot(layer, plot, "@LA"))
            return 0;
    }
    return 1;
}
