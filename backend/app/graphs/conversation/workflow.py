from app.schemas.workflow import WorkflowPlan, WorkflowStep

def advance_workflow(workflow: WorkflowPlan, completed_step: WorkflowStep) -> WorkflowPlan:
    completed_steps = list(workflow.completed_steps)

    if completed_step not in completed_steps:
        completed_steps.append(completed_step)

    try:
        current_index = workflow.steps.index(completed_step)
    except ValueError:
        return workflow.model_copy(
            update={
                "completed_steps": completed_steps,
            }
        )

    next_index = current_index + 1

    if next_index >= len(workflow.steps):
        next_step =  WorkflowStep.COMPLETED
    else:
        next_step = workflow.steps[next_index]

    return workflow.model_copy(
        update={
            "current_step": next_step,
            "completed_steps": completed_steps,
        }
    )
    