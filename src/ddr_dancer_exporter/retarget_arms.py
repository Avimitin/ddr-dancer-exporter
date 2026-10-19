"""Rebind source arm geometry to the DDR rest frame before writing KTMDL."""
import numpy as np

def rotation_between(a,b):
    a=np.asarray(a)/np.linalg.norm(a);b=np.asarray(b)/np.linalg.norm(b)
    c=float(np.clip(a@b,-1,1));v=np.cross(a,b)
    if c < -1+1e-8:
        axis=np.eye(3)[np.argmin(np.abs(a))];axis=np.cross(a,axis);axis/=np.linalg.norm(axis)
        return 2*np.outer(axis,axis)-np.eye(3)
    k=np.array([[0,-v[2],v[1]],[v[2],0,-v[0]],[-v[1],v[0],0]])
    return (np.eye(3)+k+k@k/(1+c)).T

def retarget(pos,normals,ids,weights,source,mapping,ref,scale,origin,config):
    names={b['name']:b['index'] for b in mapping['ddr_bones']}
    rest=np.array([b['matrix'] for b in ref['bones']])
    anchors={};tails={}
    if 'arm_bind' in source:
        for key,value in source['arm_bind'].items():
            anchors[key]=np.array(value['head']);tails[key]=np.array(value['tail'])
    else:
        # PMX records retain real source bone positions, unlike older Blender intermediates.
        for row in mapping['mapping']:
            key=row['target_candidate']
            if key in {p+s for p in ('Left','Right') for s in ('Collar','Arm','ForeArm','Hand')}:
                anchors[key]=np.array(source['bones'][row['source_index']]['position'])
    for dic in (anchors,tails):
        for key,p in dic.items():dic[key]=(p-origin)*scale*np.array([1,1,-1])
    transforms={};checks=[]
    for prefix in ('Left','Right'):
        for part,nextpart in [('Collar','Arm'),('Arm','ForeArm'),('ForeArm','Hand'),('Hand',None)]:
            key=prefix+part
            if key not in anchors:raise ValueError('Missing source rest joint '+key+'; re-import the source model')
            head=anchors[key];dest=rest[names[key],3,:3]
            if nextpart:
                end=anchors[prefix+nextpart];destend=rest[names[prefix+nextpart],3,:3]
                axis=end-head;targetaxis=destend-dest
                lengthscale=np.linalg.norm(targetaxis)/np.linalg.norm(axis)
            else:
                axis=tails[key]-head if key in tails else head-anchors[prefix+'ForeArm']
                targetaxis=dest-rest[names[prefix+'ForeArm'],3,:3];lengthscale=1.
            rot=rotation_between(axis,targetaxis)
            # Scale only along the bone. Preserve arm/wing thickness.
            unit=axis/np.linalg.norm(axis)
            linear=(np.eye(3)+(lengthscale-1)*np.outer(unit,unit))@rot
            transforms[names[key]]=(head,dest,linear)
            if part in ('Arm','ForeArm'):transforms[names[key+'Roll']]=(head,dest,linear)
            check=dict(bone=key,pivot_error_before=float(np.linalg.norm(head-dest)),pivot_error_after=0.,direction_error_after=float(np.linalg.norm((axis@rot)/np.linalg.norm(axis)-targetaxis/np.linalg.norm(targetaxis))),length_scale=float(lengthscale))
            if nextpart:
                check['endpoint_error_after']=float(np.linalg.norm((end-head)@linear+dest-destend))
            checks.append(check)
    oldpos=pos.copy();newpos=np.zeros_like(pos);newnormal=np.zeros_like(normals)
    for k in range(4):
        p=oldpos.copy();n=normals.copy()
        for bi,(head,dest,linear) in transforms.items():
            mask=ids[:,k]==bi
            p[mask]=(oldpos[mask]-head)@linear+dest
            n[mask]=normals[mask]@np.linalg.inv(linear).T
        newpos+=p*weights[:,k,None];newnormal+=n*weights[:,k,None]
    newnormal/=np.maximum(np.linalg.norm(newnormal,axis=1,keepdims=True),1e-12)
    dropped=0.
    twist_mode=config.get('arm_twist_weights')
    if twist_mode is None:
        has_roll=np.any((weights>0)&np.isin(ids,[names[p+s] for p in ('Left','Right') for s in ('ArmRoll','ForeArmRoll')]))
        twist_mode='source' if has_roll else 'spatial'
    if twist_mode not in ('source','spatial'):raise ValueError('arm_twist_weights must be source or spatial')
    if twist_mode=='spatial':
        # Sources without deform twist bones need a gradual weight transition to
        # the stock roll joints; retain the same aligned mesh and limb membership.
        for vi in range(len(ids)):
            merged={}
            for bi,w in zip(ids[vi],weights[vi]):
                if w<=0:continue
                split=None
                for prefix in ('Left','Right'):
                    for part,nextpart in [('Arm','ForeArm'),('ForeArm','Hand')]:
                        if bi==names[prefix+part]:
                            a=anchors[prefix+part];axis=anchors[prefix+nextpart]-a
                            t=np.clip((oldpos[vi]-a)@axis/(axis@axis),0,1)
                            t=t*t*(3-2*t);split=(names[prefix+part+'Roll'],t)
                if split:
                    roll,t=split;merged[bi]=merged.get(bi,0)+w*(1-t);merged[roll]=merged.get(roll,0)+w*t
                else:merged[bi]=merged.get(bi,0)+w
            pairs=sorted(merged.items(),key=lambda x:-x[1]);dropped=max(dropped,sum(w for _,w in pairs[4:]));pairs=pairs[:4]
            total=sum(w for _,w in pairs);pairs=[(b,w/total) for b,w in pairs];pairs += [(pairs[0][0],0)]*(4-len(pairs))
            ids[vi]=[b for b,w in pairs];weights[vi]=[w for b,w in pairs]
    assert np.isfinite(newpos).all() and np.isfinite(newnormal).all()
    report=dict(method='Source arm and collar rest frames to DDR anchors; segment length correction preserves cross-section; skin-weight blended transforms',twist_weights=twist_mode,joints=checks,max_dropped_weight=dropped,roll_weight_sums={key:float(weights[ids==names[key]].sum()) for key in ('LeftArmRoll','RightArmRoll','LeftForeArmRoll','RightForeArmRoll')})
    return newpos,newnormal,ids,weights,report
