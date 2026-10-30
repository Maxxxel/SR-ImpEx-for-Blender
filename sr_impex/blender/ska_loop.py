"""Periodic SKA curve segments using Blender-native Bezier evaluation.

Boundary copies are preview support, not extra exported SKA samples. Their
snapshot lets an explicitly edited copy become an ordinary authored key.
"""
import json
import bpy

KEY='ska_loop_helpers'
_signatures={}
_records={}


def snapshot(point):
    return [list(point.co),list(point.handle_left),list(point.handle_right),point.interpolation]


def _same(point,row):
    value=snapshot(point)
    return value[3]==row[3] and all(abs(a-b)<1e-4 for v,w in zip(value[:3],row[:3]) for a,b in zip(v,w))


def authored_points(action,curve):
    raw=action.get(KEY,'[]');cache=_records.get(action.as_pointer())
    if cache is None or cache[0]!=raw:
        grouped={}
        for row in json.loads(raw):grouped.setdefault((row['path'],row['axis']),[]).append(row['point'])
        cache=(raw,grouped);_records[action.as_pointer()]=cache
    rows=cache[1].get((curve.data_path,curve.array_index),[])
    return [p for p in curve.keyframe_points if not any(_same(p,row) for row in rows)]


def _slope(point,side):
    handle=getattr(point,'handle_'+side)
    dx=handle.x-point.co.x
    return (handle.y-point.co.y)/dx if abs(dx)>1e-8 else 0.


def sync(action):
    if KEY in action and _signatures.get(action.as_pointer())==signature(action):return
    from sr_impex.utilities.ska_utility import _iter_action_fcurves
    curves=list(_iter_action_fcurves(action))
    rows=[];period=float(action.get('frame_length',0));start=float(action.get('ska_start_frame',0))
    loop=int(action.get('repeat',0))==1 and period>0
    for curve in curves:
        real=authored_points(action,curve)
        generated=[p for p in curve.keyframe_points if p not in real]
        for point in reversed(generated):curve.keyframe_points.remove(point,fast=True)
        curve.update()
        if not loop or not curve.keyframe_points:continue
        points=list(curve.keyframe_points);first,last=points[0],points[-1]
        first_x,first_y=tuple(first.co);last_x,last_y=tuple(last.co)
        first_m=_slope(first,'right');last_m=_slope(last,'left')
        # One source key can still have a nonzero Hermite tangent.
        if len(points)==1:last_m=first_m
        interpolation=last.interpolation
        additions=[]
        if first_x>start+1e-5:additions.append((last_x-period,last_y,last_m,'before'))
        if last_x<start+period-1e-5:additions.append((first_x+period,first_y,first_m,'after'))
        for x,y,slope,side in additions:
            point=curve.keyframe_points.insert(x,y,options={'FAST'})
            point.handle_left_type=point.handle_right_type='FREE'
            point.interpolation=interpolation
        curve.update()
        points=list(curve.keyframe_points)
        for index in range(len(points)-1):
            a,b=points[index:index+2]
            before=abs(a.co.x-(last_x-period))<1e-5 and first_x>start+1e-5
            after=abs(b.co.x-(first_x+period))<1e-5 and last_x<start+period-1e-5
            if not (before or after):continue
            width=(b.co.x-a.co.x)/3
            a.handle_right_type=b.handle_left_type='FREE'
            a.handle_right=(a.co.x+width,a.co.y+last_m*width)
            b.handle_left=(b.co.x-width,b.co.y-first_m*width)
        curve.update()
        for point in curve.keyframe_points:
            if any(abs(point.co.x-x)<1e-5 for x,y,slope,side in additions):
                rows.append({'path':curve.data_path,'axis':curve.array_index,'point':snapshot(point)})
    action[KEY]=json.dumps(rows,separators=(',',':'))
    _signatures[action.as_pointer()]=signature(action)


def strip(action):
    """Remove unedited copies before a user changes the clip's interpolation."""
    from sr_impex.utilities.ska_utility import _iter_action_fcurves
    for curve in _iter_action_fcurves(action):
        real=authored_points(action,curve)
        for point in reversed([p for p in curve.keyframe_points if p not in real]):
            curve.keyframe_points.remove(point,fast=True)
        curve.update()
    action[KEY]='[]';_signatures.pop(action.as_pointer(),None)


def signature(action):
    from sr_impex.utilities.ska_utility import _iter_action_fcurves
    return (action.get('repeat'),action.get('frame_length'),action.get('ska_start_frame'),
        tuple((c.data_path,c.array_index,tuple(tuple(p.co)+tuple(p.handle_left)+tuple(p.handle_right)+(p.interpolation,)
              for p in c.keyframe_points)) for c in _iter_action_fcurves(action)))


def _tick():
    if bpy.app.is_job_running('RENDER'):return .5
    # Cached boundary keys already evaluate natively during playback. Scanning
    # every key/handle here stalls large clips; refresh edits once playback stops.
    if any(w.screen.is_animation_playing for w in bpy.context.window_manager.windows):return .5
    actions={o.animation_data.action for o in bpy.context.scene.objects
             if o.type=='ARMATURE' and o.animation_data and o.animation_data.action}
    for action in actions:
        if KEY not in action:continue
        if _signatures.get(action.as_pointer())!=signature(action):sync(action)
    return .5


def register():
    if not bpy.app.timers.is_registered(_tick):bpy.app.timers.register(_tick,first_interval=.5,persistent=True)


def unregister():
    if bpy.app.timers.is_registered(_tick):bpy.app.timers.unregister(_tick)
    _signatures.clear();_records.clear()
