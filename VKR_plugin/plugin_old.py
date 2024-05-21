from abaqus import *
from abaqusConstants import *

from part import *
from material import *
from section import *
from assembly import *
from step import *
from interaction import *
from load import *
from mesh import *
from optimization import *
from job import *
from sketch import *
from visualization import *
from connectorBehavior import *
import sys


def setPredefinedStress(model, region, data, name, distributionType):
    if len(data) == 3:
        model.Stress(distributionType=distributionType, name=name,
                     region=region,
                     sigma11=data[0], sigma22=data[1], sigma33=data[2])
    elif len(data) == 4:
        model.Stress(distributionType=distributionType, name=name,
                     region=region,
                     sigma11=data[0], sigma22=data[1], sigma33=data[2], sigma12=data[3])
    elif len(data) == 5:
        model.Stress(distributionType=distributionType, name=name,
                     region=region,
                     sigma11=data[0], sigma22=data[1], sigma33=data[2], sigma12=data[3], sigma13=data[4])
    else:
        model.Stress(distributionType=distributionType, name=name,
                     region=region,
                     sigma11=data[0], sigma22=data[1], sigma33=data[2],
                     sigma12=data[3], sigma13=data[4], sigma23=data[5])

def setPredefinedStrain(model, region, data, name, distributionType):
    model.KinematicHardening(distributionType=distributionType, name=name,
                             region=region,
                             backStress=((0.0, 0.0, 0.0, 0.0, 0.0, 0.0),), numBackStress=1,
                             equivPlasticStrain=(data,), field='', )

def createNewModel(newModel, lastModel, lastJob, part, material):
    # Making the part correspond to the one from odb.
    part = part.upper() + '-1'

    # Creating the Model with specified name.
    mdb.Model(modelType=STANDARD_EXPLICIT, name=newModel)

    # Opening data base and importing part mesh.
    odb = session.openOdb(r'C:/temp/' + lastJob + '.odb')
    model = mdb.models[newModel]
    model.PartFromOdb(frame=len(odb.steps['Step-1'].frames) - 1, instance=part, name=
    part, odb=odb, shape=DEFORMED, step=0)

    # Copying the material from previous step and setting it to the part
    model.copyMaterials(sourceModel=mdb.models[lastModel])
    model.HomogeneousSolidSection(material=material, name=
    'Section-1', thickness=None)
    model.parts[part].SectionAssignment(offset=0.0,
                                        offsetField='', offsetType=MIDDLE_SURFACE, region=Region(
            elements=mdb.models[newModel].parts[part].elements), sectionName='Section-1',
                                        thicknessAssignment=FROM_SECTION)

    # Creating an assembly.
    model.rootAssembly.DatumCsysByDefault(CARTESIAN)
    model.rootAssembly.Instance(dependent=ON, name=part,
                                part=mdb.models[newModel].parts[part])

    # Getting stress and strain information from the data base.
    lastframe = odb.steps['Step-1'].frames[-1]
    stress = lastframe.fieldOutputs['S']
    strain = lastframe.fieldOutputs['PEEQ']
    elements = model.rootAssembly.instances[part].elements

    # Setting the information to the current part during the Inital State.
    for i in range(0, len(elements)):
        stress_value = stress.values[i]
        strain_value = strain.values[i]
        element = elements[i]
        region = Region(elements=MeshElementArray([element]))

        setPredefinedStress(model, region, stress_value.data, 'Stress PF-' + str(i), UNIFORM)
        setPredefinedStrain(model, region, strain_value.data, 'Strain PF-' + str(i), MAGNITUDE)

    # Creating a Job to run a pass of the simulation.
    mdb.Job(atTime=None, contactPrint=OFF, description='', echoPrint=OFF,
            explicitPrecision=SINGLE, getMemoryFromAnalysis=True, historyPrint=OFF,
            memory=90, memoryUnits=PERCENTAGE, model=newModel, modelPrint=OFF,
            multiprocessingMode=DEFAULT, name=lastJob + '-1', nodalOutputPrecision=SINGLE,
            numCpus=4, numDomains=4, numGPUs=0, numThreadsPerMpiProcess=1, queue=None,
            resultsFormat=ODB, scratch='', type=ANALYSIS, userSubroutine='', waitHours=
            0, waitMinutes=0)
