from app.extensions import db

class QueuePriorityRule(db.Model):
    __tablename__ = 'queue_priority_rules'

    id = db.Column(db.Integer, primary_key=True)
    category_name = db.Column(db.String(50), unique=True, nullable=False)
    priority_weight = db.Column(db.Integer, nullable=False, default=50) # Higher = Priority first
    is_active = db.Column(db.Boolean, default=True)

    @staticmethod
    def get_priority_weight(priority_name: str) -> int:
        """Returns numeric priority weight for sorting. Defaults to 50 if unknown."""
        rule = QueuePriorityRule.query.filter_by(category_name=priority_name, is_active=True).first()
        if rule:
            return rule.priority_weight
        
        # Hardcoded fallback weights
        weights = {
            'Emergency': 100,
            'Senior Citizen': 80,
            'Pregnant Woman': 70,
            'Child': 60,
            'Regular': 50
        }
        return weights.get(priority_name, 50)

    def __repr__(self):
        return f"<QueuePriorityRule {self.category_name} Weight: {self.priority_weight}>"
