"""Verified vertical constraints from the two Alt-4 CAD sections.

Keep these measurements separate from plan registration. In particular, a clear
height is not a floor elevation increment, and a circular radius is not a rise.
"""
import math
from cad_text import decode_architect_text


def section_constraints(doc):
    def measurement(handle):
        dimension=doc.entitydb[handle]
        a,b=dimension.dxf.defpoint2,dimension.dxf.defpoint3
        projected=abs(b.y-a.y)/100
        stated=dimension.dxf.actual_measurement/100
        if not math.isclose(projected,stated,abs_tol=.0001):
            raise ValueError(f'Section dimension {handle} conflicts with its endpoints')
        return round(stated,4)

    outer=doc.entitydb['975']
    inner=doc.entitydb['858']
    finish=doc.entitydb['9BF']
    lower=doc.entitydb['B6F']
    ground_y=doc.entitydb['82C'].dxf.defpoint2.y
    lower_ground_y=doc.entitydb['750'].dxf.defpoint2.y
    if not math.isclose(outer.dxf.radius,lower.dxf.radius,abs_tol=.0001):
        raise ValueError('Roof section radii disagree')
    if not math.isclose(outer.dxf.center.y-ground_y,lower.dxf.center.y-lower_ground_y,abs_tol=.0001):
        raise ValueError('Roof sections disagree on their vertical datum')
    levels={
        'basement':-measurement('1747'),
        'ground':0,
        'living':measurement('A04'),
        'topLower':round((doc.entitydb['97B'].dxf.defpoint3.y-ground_y)/100,4),
        'topHigher':round((doc.entitydb['7D4'].dxf.defpoint2.y-ground_y)/100,4),
    }
    return {
        'source':'Two user-identified cut sections in Alt-4',
        'layers':['A10','A11','A13','A14','A17','A24','A49'],
        'cuts':[{'handle':h,'label':decode_architect_text(doc.entitydb[h].dxf.text)} for h in ('923','A58')],
        'roof':{
            'profile':'circular, asymmetric trims; not a symmetric ellipse',
            'outerRadius':outer.dxf.radius/100,
            'innerRadius':inner.dxf.radius/100,
            'finishRadius':finish.dxf.radius/100,
            'shellRadialThickness':round((outer.dxf.radius-inner.dxf.radius)/100,4),
            'centerElevation':round((outer.dxf.center.y-ground_y)/100,4),
            'structuralCrownElevation':round((outer.dxf.center.y+outer.dxf.radius-ground_y)/100,4),
            'finishedCrownElevation':round((finish.dxf.center.y+finish.dxf.radius-ground_y)/100,4),
            'sourceHandles':['975','858','9BF','B6F','C73','C76','9C7','C82'],
        },
        'levels':levels,
        'clearHeights':{'basement':measurement('8C6'),'ground':measurement('82C'),'livingLowZone':measurement('988')},
        'floorToFloor':{'basementToGround':measurement('1747'),'groundToLiving':measurement('A04')},
        'interstoryDepth':measurement('839'),
        'topLevelDifference':round(levels['topHigher']-levels['topLower'],4),
        'sourceDimensionHandles':['1747','A04','82C','839','8C6','988','97B','7D4'],
        'pending':['Register section stations to plan cut lines',
                   'Resolve top-floor high/low zone boundaries and connecting steps',
                   'Apply section-driven ceiling, wall and roof profiles to the renderer'],
    }
