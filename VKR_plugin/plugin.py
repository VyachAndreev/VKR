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


def setPredefinedStress(model, region, data, name, distribution_type):
    if len(data) == 3:
        model.Stress(distributionType=distribution_type, name=name,
                     region=region,
                     sigma11=data[0], sigma22=data[1], sigma33=data[2])
    elif len(data) == 4:
        model.Stress(distributionType=distribution_type, name=name,
                     region=region,
                     sigma11=data[0], sigma22=data[1], sigma33=data[2], sigma12=data[3])
    elif len(data) == 5:
        model.Stress(distributionType=distribution_type, name=name,
                     region=region,
                     sigma11=data[0], sigma22=data[1], sigma33=data[2], sigma12=data[3], sigma13=data[4])
    else:
        model.Stress(distributionType=distribution_type, name=name,
                     region=region,
                     sigma11=data[0], sigma22=data[1], sigma33=data[2],
                     sigma12=data[3], sigma13=data[4], sigma23=data[5])


def setPredefinedStrain(model, region, data, name, distribution_type):
    model.KinematicHardening(distributionType=distribution_type, name=name,
                             region=region,
                             backStress=((0.0, 0.0, 0.0, 0.0, 0.0, 0.0),), numBackStress=1,
                             equivPlasticStrain=(data,), field='', )


def getNoneNegativeValue(a):
    if a < 0:
        return 0
    return a


def fixModelNodesCoordinatesIfNecessary(assembly, elements):
    for element in elements:
        for node in element.getNodes():
            coordinates = node.coordinates
            newCoordinates = []
            for coordinate in node.coordinates:
                newCoordinates.append(getNoneNegativeValue(coordinate))
            assembly.editNode(
                nodes=(node,),
                coordinate1=newCoordinates[0], coordinate2=newCoordinates[1], coordinate3=newCoordinates[2]
            )
            if newCoordinates != coordinates:
                print "node changed:"
                print coordinates
                print newCoordinates


def createIntermediateModel(lastModel, lastJob, part, material):
    print 'createIntermediateModel'
    # Making the part correspond to the one from odb.
    intermediate_part_name = part.upper() + '-1'

    # Creating the Model with specified name.
    intermediate_model_name = lastModel + '-intermediate'
    intermediate_model = mdb.Model(modelType=STANDARD_EXPLICIT, name=intermediate_model_name)

    # Opening data base and importing part mesh.
    odb = session.openOdb(r'C:/temp/' + lastJob + '.odb')
    intermediate_model.PartFromOdb(frame=len(odb.steps['Step-1'].frames) - 1, instance=intermediate_part_name,
                                   name=intermediate_part_name, odb=odb, shape=DEFORMED, step=0)

    # Copying the material from previous step and setting it to the part
    intermediate_model.copyMaterials(sourceModel=mdb.models[lastModel])

    section_name = 'Section-1'
    intermediate_model.HomogeneousSolidSection(material=material, name=
    section_name, thickness=None)
    intermediate_part = intermediate_model.parts[intermediate_part_name]
    intermediate_part.SectionAssignment(
        offset=0.0, offsetField='', offsetType=MIDDLE_SURFACE,
        region=Region(elements=intermediate_part.elements),
        sectionName=section_name, thicknessAssignment=FROM_SECTION
    )

    step_name = 'Step-1'
    intermediate_model.StaticStep(name=step_name, previous='Initial')
    intermediate_model.steps[step_name].Restart(frequency=1, numberIntervals=0, overlay=OFF, timeMarks=OFF)

    # Creating an assembly.
    intermediate_assembly = intermediate_model.rootAssembly
    intermediate_assembly.DatumCsysByDefault(CARTESIAN)
    intermediate_part_instance = intermediate_assembly.Instance(dependent=ON, name=intermediate_part_name,
                                                                part=intermediate_part)

    # Getting stress and strain information from the data base.
    lastframe = odb.steps['Step-1'].frames[-1]
    stress = lastframe.fieldOutputs['S']
    strain = lastframe.fieldOutputs['PEEQ']
    elements = intermediate_part_instance.elements

    # Setting the information to the current part during the Inital State.
    for i in range(0, len(elements)):
        stress_value = stress.values[i]
        strain_value = strain.values[i]
        element = elements[i]
        region = Region(elements=MeshElementArray([element]))

        setPredefinedStress(intermediate_model, region, stress_value.data, 'Stress PF-' + str(i), UNIFORM)
        setPredefinedStrain(intermediate_model, region, strain_value.data, 'Strain PF-' + str(i), MAGNITUDE)

    # Creating a Job to run a pass of the simulation.
    job_name = lastJob + '-intermediate'
    intermidiate_job = mdb.Job(atTime=None, contactPrint=OFF, description='', echoPrint=OFF,
                               explicitPrecision=SINGLE, getMemoryFromAnalysis=True, historyPrint=OFF,
                               memory=90, memoryUnits=PERCENTAGE, model=intermediate_model_name, modelPrint=OFF,
                               multiprocessingMode=DEFAULT, name=job_name, nodalOutputPrecision=SINGLE,
                               numCpus=4, numDomains=4, numGPUs=0, numThrseadsPerMpiProcess=1, queue=None,
                               resultsFormat=ODB, scratch='', type=ANALYSIS, userSubroutine='', waitHours=
                               0, waitMinutes=0)

    print 'before fixing'

    fixModelNodesCoordinatesIfNecessary(intermediate_assembly, elements)

    print 'after fixing'

    intermidiate_job.submit(consistencyChecking=OFF)
    intermidiate_job.waitForCompletion()

    return intermediate_model


def createNewModel(newModel, lastModel, lastJob, part, material):
    intermediate_model = createIntermediateModel(lastModel, lastJob, part, material)
    print 'hello world!'
    new_model = mdb.Model(name=newModel, objectToCopy=intermediate_model)
    new_model.keywordBlock.synchVersions(storeNodesAndElements=False)
    sieBlocks = new_model.keywordBlock.sieBlocks
    blockCount = -1
    for block in sieBlocks:
        if "STEP" in block:
            stepBlock = block
            break
        blockCount += 1
    new_model.keywordBlock.insert(blockCount,
                                             '\n*MAP SOLUTION, UNBALANCED STRESS=STEP')
    mdb.Job(atTime=None, contactPrint=OFF, description='', echoPrint=OFF,
            explicitPrecision=SINGLE, getMemoryFromAnalysis=True, historyPrint=OFF,
            memory=90, memoryUnits=PERCENTAGE, model=newModel, modelPrint=OFF,
            multiprocessingMode=DEFAULT, name=lastJob + '-next', nodalOutputPrecision=SINGLE,
            numCpus=1, numGPUs=0, numThreadsPerMpiProcess=1, queue=None, resultsFormat=
            ODB, scratch='', type=ANALYSIS, userSubroutine='', waitHours=0,
            waitMinutes=0)
    predefinedFields = new_model.predefinedFields
    for key in predefinedFields.keys():
        del predefinedFields[key]
