from polyaxon import tracking

tracking.init(project="demo", tags=["examples"])
tracking.log_confusion_matrix(
    name="confusion",
    z=[[0.1, 0.3, 0.5, 0.2], [1.0, 0.8, 0.6, 0.1], [0.1, 0.3, 0.6, 0.9], [0.6, 0.4, 0.2, 0.2]],
    x=['healthy', 'multiple diseases', 'rust', 'scab'],
    y=['healthy', 'multiple diseases', 'rust', 'scab'],
    step=1,
)
