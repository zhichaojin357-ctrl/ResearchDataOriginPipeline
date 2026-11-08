#include <Origin.h>

// Logical page coordinates, verified against Origin's displayed object bounds.
// GetRect can return [-1,-1,0,0] for a valid legend in current Origin builds.
static bool rdop_legend_layer_box(GraphLayer& layer, vector& box)
{
    double pos[4]; // Origin order is width, height, left, top.
    int units = layer.GetPosition(pos);
    if (!layer.UnitsConvert(M_PIXEL, pos, units) || pos[0] <= 0 || pos[1] <= 0)
        return false;
    box.SetSize(4);
    box[0] = pos[2]; box[1] = pos[3];
    box[2] = pos[2] + pos[0]; box[3] = pos[3] + pos[1];
    return true;
}

static bool rdop_is_native_legend(GraphLayer& layer, GraphObject& go)
{
    int kind;
    go.GetObjectType(&kind);
    if (kind != GROBJ_TN_TEXT) return false;
    double show = 0;
    string text = go.Text;
    return layer.IsShow(LAYER_CHECK_SHOW_LABELS) &&
        layer.LT_get_var(go.GetName() + ".show", &show) && show > 0.5 &&
        text.Find("\\l(") >= 0 && text.Find("%(") >= 0;
}

// Slab clipping includes endpoints and segments crossing a box with both
// endpoints outside. Missing points are handled by the caller, never joined.
static bool rdop_legend_segment_hit(double x0, double y0, double x1, double y1, vector& box)
{
    if ((x0<box[0] && x1<box[0]) || (x0>box[2] && x1>box[2]) ||
        (y0<box[1] && y1<box[1]) || (y0>box[3] && y1>box[3])) return false;
    double lo = 0, hi = 1;
    for (int axis = 0; axis < 2; axis++)
    {
        double start = axis ? y0 : x0, delta = axis ? y1-y0 : x1-x0;
        if (delta == 0)
        {
            if (start < box[axis] || start > box[axis+2]) return false;
        }
        else
        {
            double a = (box[axis]-start)/delta, b = (box[axis+2]-start)/delta;
            lo = max(lo, min(a,b)); hi = min(hi, max(a,b));
            if (lo > hi) return false;
        }
    }
    return true;
}

// Ordinary straight XY line/scatter products only; not a spline/area/bar renderer.
// This cache belongs to one invocation only. No sampling, data edits or
// repeated Origin data/coordinate calls during candidate evaluation.
static bool rdop_cache_legend_curves(GraphPage& page,
    vector& cx0, vector& cy0, vector& cx1, vector& cy1,
    vector<int>& clayer, double& stroke_radius)
{
    stroke_radius=0;
    foreach (GraphLayer layer in page.Layers)
    {
        if (!layer.IsShow(LAYER_CHECK_SHOW_DATA)) continue;
        int layer_index=layer.GetIndex();
        foreach (DataPlot plot in layer.DataPlots)
        {
            if (!plot.IsShow()) continue;
            int type = plot.GetPlotType();
            // The adaptive XRD executor explicitly declares its unstacked,
            // zero-baseline reference column plot. Conservatively exclude the
            // entire layer width over its occupied vertical range, including
            // the filled interior; never approximate bars by their tips.
            double zero_column=0;
            LT_get_var("__rdop_zero_column", &zero_column);
            if (type==IDM_PLOT_COLUMN && layer_index==0 && plot.GetIndex()+1==zero_column)
            {
                vector bx, by, bounds;
                if (!rdop_legend_layer_box(layer,bounds) ||
                    plot.GetDataPoints(0,-1,bx,by,NULL,NULL,GETDATAPTS_SCREEN_POSITION)<0 ||
                    bx.GetSize()!=by.GetSize()) return false;
                int px, py;
                bool any=false;
                double top=0, bottom=0;
                for (int item=0; item<bx.GetSize(); item++)
                {
                    if (bx[item]==NANUM || by[item]==NANUM) continue;
                    if (!layer.WorldToPage(px,py,bx[item],by[item])) return false;
                    if (!any) { top=py; bottom=py; any=true; }
                    top=min(top,py); bottom=max(bottom,py);
                    if (!layer.WorldToPage(px,py,bx[item],0)) return false;
                    top=min(top,py); bottom=max(bottom,py);
                }
                if (!any) return false;
                cx0.Add(bounds[0]); cy0.Add(top);
                cx1.Add(bounds[2]); cy1.Add(bottom);
                clayer.Add(-layer_index-1);
                continue;
            }
            if (type != IDM_PLOT_LINE && type != IDM_PLOT_SCATTER && type != IDM_PLOT_LINESYMB) return false;
            string command;
            command.Format("range __rdop_curve=[%s]%d!%d; __rdop_width=nan; __rdop_size=nan; get __rdop_curve -wp __rdop_width;",
                page.GetName(),layer_index+1,plot.GetIndex()+1);
            bool symbols=type==IDM_PLOT_SCATTER || type==IDM_PLOT_LINESYMB;
            if (symbols) command+=" get __rdop_curve -z __rdop_size;";
            double width=NANUM, size=0;
            if (!layer.LT_execute(command) || !layer.LT_get_var("__rdop_width",&width) || width==NANUM || width<0) return false;
            if (symbols && (!layer.LT_get_var("__rdop_size",&size) || size==NANUM || size<0)) return false;
            // Native widths are points; page logical units are 0.001 inch.
            stroke_radius=max(stroke_radius,max(width,size)*1000/144);
            vector x, y;
            if (plot.GetDataPoints(0,-1,x,y,NULL,NULL,GETDATAPTS_SCREEN_POSITION) < 0 || x.GetSize()!=y.GetSize()) return false;
            bool previous=false;
            int px, py, last_x=0, last_y=0;
            for (int index=0; index<x.GetSize(); index++)
            {
                if (x[index]==NANUM || y[index]==NANUM) { previous=false; continue; }
                if (!layer.WorldToPage(px,py,x[index],y[index])) return false;
                bool connected=previous && type!=IDM_PLOT_SCATTER;
                cx0.Add(connected ? last_x : px); cy0.Add(connected ? last_y : py);
                cx1.Add(px); cy1.Add(py);
                clayer.Add(layer_index);
                last_x=px; last_y=py; previous=true;
            }
        }
    }
    return true;
}

static int rdop_legend_box_clear(GraphPage& page, GraphLayer& owner,
    GraphObject& target, vector& box, double gap,
    vector& cx0, vector& cy0, vector& cx1, vector& cy1,
    vector<int>& clayer, vector<int>& legend_layers,
    vector<string>& legend_names, vector<int>& pending)
{
    vector padded;
    padded = box;
    padded[0] -= gap; padded[1] -= gap; padded[2] += gap; padded[3] += gap;
    vector owner_bounds;
    double percent[4];
    int units=owner.GetPosition(percent);
    if (!rdop_legend_layer_box(owner,owner_bounds) || !owner.UnitsConvert(M_PERCENT,percent,units) ||
        percent[0]<=0 || percent[1]<=0) return -1;
    double page_width=(owner_bounds[2]-owner_bounds[0])*100/percent[0];
    double page_height=(owner_bounds[3]-owner_bounds[1])*100/percent[1];
    if (padded[0]<0 || padded[1]<0 || padded[2]>page_width || padded[3]>page_height)
        return 0;
    foreach (GraphLayer layer in page.Layers)
    {
        vector bounds;
        if (!rdop_legend_layer_box(layer, bounds)) return -1;
        // Keep distance from all visible layer borders/axes, including insets.
        if ((layer.IsShow(LAYER_CHECK_SHOW_X) || layer.IsShow(LAYER_CHECK_SHOW_Y)) &&
            (rdop_legend_segment_hit(bounds[0],bounds[1],bounds[2],bounds[1],padded) ||
             rdop_legend_segment_hit(bounds[0],bounds[3],bounds[2],bounds[3],padded) ||
             rdop_legend_segment_hit(bounds[0],bounds[1],bounds[0],bounds[3],padded) ||
             rdop_legend_segment_hit(bounds[2],bounds[1],bounds[2],bounds[3],padded)))
            return 0;
        foreach (GraphObject other in layer.GraphObjects)
        {
            if (layer.GetIndex() == owner.GetIndex() && other.GetName() == target.GetName()) continue;
            bool deferred=false;
            string other_name=other.GetName();
            for (int item=0; item<pending.GetSize(); item++)
            {
                if (!pending[item] || legend_layers[item]!=layer.GetIndex()) continue;
                string pending_name=legend_names[item];
                if (pending_name==other_name) { deferred=true; break; }
            }
            if (deferred) continue;
            double show=0;
            // Existing annotations/axis titles are obstacles too, never moved.
            if (layer.IsShow(LAYER_CHECK_SHOW_LABELS) &&
                layer.LT_get_var(other.GetName()+".show",&show) && show>0.5 &&
                other.Width>0 && other.Height>0 &&
                other.Left <= padded[2] && other.Left+other.Width >= padded[0] &&
                other.Top <= padded[3] && other.Top+other.Height >= padded[1])
                return 0;
        }
        if (!layer.IsShow(LAYER_CHECK_SHOW_DATA)) continue;
        // Curves are clipped to their own layer, not the legend's layer.
        vector clipped;
        clipped = padded;
        clipped[0] = max(clipped[0],bounds[0]); clipped[1] = max(clipped[1],bounds[1]);
        clipped[2] = min(clipped[2],bounds[2]); clipped[3] = min(clipped[3],bounds[3]);
        if (clipped[0] > clipped[2] || clipped[1] > clipped[3]) continue;
        int layer_index=layer.GetIndex();
        for (int index=0; index<cx0.GetSize(); index++)
        {
            if (clayer[index]==-layer_index-1 &&
                cx0[index]<=clipped[2] && cx1[index]>=clipped[0] &&
                cy0[index]<=clipped[3] && cy1[index]>=clipped[1]) return 0;
            if (clayer[index]==layer_index &&
                rdop_legend_segment_hit(cx0[index],cy0[index],cx1[index],cy1[index],clipped))
                return 0;
        }
    }
    return 1;
}

// Page-wide transaction: freeze legal original anchors, then place invalid
// legends largest first on the same nearest-first 33x33 interior grid.
// 1 unchanged, 2 moved, 0 no free candidate, -1 geometry unsupported/unreadable.
int rdop_place_legends()
{
    GraphLayer active = Project.ActiveLayer();
    if (!active) return -1;
    GraphPage page = active.GetPage();
    vector<int> layers, lefts, tops;
    vector<string> names;
    foreach (GraphLayer layer in page.Layers)
    {
        foreach (GraphObject go in layer.GraphObjects)
        {
            if (rdop_is_native_legend(layer,go))
            {
                layers.Add(layer.GetIndex()); names.Add(go.GetName());
                lefts.Add(go.Left); tops.Add(go.Top);
            }
        }
    }
    vector cx0, cy0, cx1, cy1;
    vector<int> clayer;
    double stroke_radius=0;
    if (names.GetSize()>0 && !rdop_cache_legend_curves(page,cx0,cy0,cx1,cy1,clayer,stroke_radius)) return -1;
    double gap=8+stroke_radius;
    vector<int> pending;
    vector<int> invalid;
    pending.SetSize(names.GetSize());
    pending=0;
    vector areas;
    // First classify against every original object; no anchors have moved and
    // no pending object is ignored until the entire classification is complete.
    for (int check_index=0; check_index<names.GetSize(); check_index++)
    {
        GraphLayer owner=page.Layers(layers[check_index]);
        GraphObject legend=owner.GraphObjects(names[check_index]);
        vector box(4);
        if (legend.Width<=0 || legend.Height<=0) return -1;
        box[0]=legend.Left; box[1]=legend.Top; box[2]=box[0]+legend.Width; box[3]=box[1]+legend.Height;
        int clear=rdop_legend_box_clear(page,owner,legend,box,gap,cx0,cy0,cx1,cy1,clayer,layers,names,pending);
        if (clear<0) return -1;
        if (!clear)
        {
            double width=legend.Width;
            double height=legend.Height;
            invalid.Add(check_index); areas.Add(width*height);
        }
    }
    for (int pending_index=0; pending_index<invalid.GetSize(); pending_index++) pending[invalid[pending_index]]=1;
    vector<uint> processing_order;
    if (invalid.GetSize()>1)
    {
        if (!areas.Sort(SORT_DESCENDING,TRUE,processing_order,SORTCNTRL_STABLE_ALGORITHM)) return -1;
    }
    else if (invalid.GetSize()==1) processing_order.Add(0);
    int moved=0, result=1;
    for (int position=0; position<processing_order.GetSize(); position++)
    {
        // Resolve through a separate order; original names/anchors remain intact for rollback.
        int item=invalid[processing_order[position]];
        GraphLayer owner=page.Layers(layers[item]);
        GraphObject legend=owner.GraphObjects(names[item]);
        vector bounds, box(4);
        if (!rdop_legend_layer_box(owner,bounds) || legend.Width<=0 || legend.Height<=0) { result=-1; break; }
        box[0]=legend.Left; box[1]=legend.Top; box[2]=box[0]+legend.Width; box[3]=box[1]+legend.Height;
        int clear=rdop_legend_box_clear(page,owner,legend,box,gap,cx0,cy0,cx1,cy1,clayer,layers,names,pending);
        if (clear<0) { result=-1; break; }
        if (clear==1) { pending[item]=0; continue; }
        bool found=false;
        double width=legend.Width, height=legend.Height;
        double xmin=bounds[0]+gap+1, ymin=bounds[1]+gap+1;
        double xmax=bounds[2]-gap-width-1, ymax=bounds[3]-gap-height-1;
        if (xmax>=xmin && ymax>=ymin)
        {
            vector distances(1089);
            vector<uint> order;
            for (int grid=0; grid<1089; grid++)
            {
                double dx=xmin+(xmax-xmin)*(grid%33)/32-lefts[item];
                double dy=ymin+(ymax-ymin)*(grid/33)/32-tops[item];
                distances[grid]=dx*dx+dy*dy;
            }
            // Stable Origin sort preserves the previous lowest-grid-index tie break.
            if (!distances.Sort(SORT_ASCENDING,TRUE,order,SORTCNTRL_STABLE_ALGORITHM))
                { result=-1; break; }
            for (int candidate=0; candidate<1089; candidate++)
            {
                int nearest=order[candidate];
                box[0]=xmin+(xmax-xmin)*(nearest%33)/32;
                box[1]=ymin+(ymax-ymin)*(nearest/33)/32;
                box[2]=box[0]+width; box[3]=box[1]+height;
                clear=rdop_legend_box_clear(page,owner,legend,box,gap,cx0,cy0,cx1,cy1,clayer,layers,names,pending);
                if (clear<0) { result=-1; break; }
                if (!clear) continue;
                legend.Left=(int)box[0]; legend.Top=(int)box[1];
                box[0]=legend.Left; box[1]=legend.Top; box[2]=box[0]+legend.Width; box[3]=box[1]+legend.Height;
                if (rdop_legend_box_clear(page,owner,legend,box,gap,cx0,cy0,cx1,cy1,clayer,layers,names,pending)!=1) { result=-1; break; }
                pending[item]=0; found=true; moved++; break;
            }
        }
        if (!found) { if (result>0) result=0; break; }
    }
    if (result<=0)
        for (int item=0; item<names.GetSize(); item++)
        {
            GraphLayer owner=page.Layers(layers[item]);
            GraphObject legend=owner.GraphObjects(names[item]);
            legend.Left=lefts[item]; legend.Top=tops[item];
        }
    LT_set_var("__rdop_legends_moved", result>0 ? moved : 0);
    LT_set_var("__rdop_legends_checked", names.GetSize());
    return result>0 && moved ? 2 : result;
}
