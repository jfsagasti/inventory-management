<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="isOpen && backlogItem" class="modal-overlay" @click="close">
        <div class="modal-container" @click.stop>
          <div class="modal-header">
            <h3 class="modal-title">
              {{ isViewMode ? 'Purchase Order' : 'Create Purchase Order' }}
            </h3>
            <button class="close-button" @click="close">
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                <path d="M15 5L5 15M5 5L15 15" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
              </svg>
            </button>
          </div>

          <div class="modal-body">
            <div class="item-header">
              <div class="item-title-section">
                <h4 class="item-name">{{ translateProductName(backlogItem.item_name) }}</h4>
                <div class="item-sku">SKU: {{ backlogItem.item_sku }} &middot; Order {{ backlogItem.order_id }}</div>
              </div>
              <span class="priority-badge" :class="backlogItem.priority">
                {{ backlogItem.priority }} Priority
              </span>
            </div>

            <div class="shortage-banner">
              <div class="shortage-label">Shortage to cover</div>
              <div class="shortage-value">{{ shortage }} units</div>
            </div>

            <!-- VIEW MODE -->
            <div v-if="isViewMode">
              <div v-if="loading" class="loading">Loading purchase order...</div>
              <div v-else-if="loadError" class="error">{{ loadError }}</div>
              <div v-else-if="purchaseOrder" class="info-grid">
                <div class="info-item">
                  <div class="info-label">PO Number</div>
                  <div class="info-value po-id">{{ purchaseOrder.id }}</div>
                </div>
                <div class="info-item">
                  <div class="info-label">Supplier</div>
                  <div class="info-value">{{ purchaseOrder.supplier_name }}</div>
                </div>
                <div class="info-item">
                  <div class="info-label">Quantity</div>
                  <div class="info-value">{{ purchaseOrder.quantity }} units</div>
                </div>
                <div class="info-item">
                  <div class="info-label">Unit Cost</div>
                  <div class="info-value">{{ formatCurrency(purchaseOrder.unit_cost) }}</div>
                </div>
                <div class="info-item">
                  <div class="info-label">Total Cost</div>
                  <div class="info-value strong">
                    {{ formatCurrency(purchaseOrder.quantity * purchaseOrder.unit_cost) }}
                  </div>
                </div>
                <div class="info-item">
                  <div class="info-label">Status</div>
                  <div class="info-value">
                    <span class="badge info">{{ purchaseOrder.status }}</span>
                  </div>
                </div>
                <div class="info-item">
                  <div class="info-label">Created</div>
                  <div class="info-value">{{ formatDate(purchaseOrder.created_date) }}</div>
                </div>
                <div class="info-item">
                  <div class="info-label">Expected Delivery</div>
                  <div class="info-value">{{ formatDate(purchaseOrder.expected_delivery_date) }}</div>
                </div>
                <div v-if="purchaseOrder.notes" class="info-item full-width">
                  <div class="info-label">Notes</div>
                  <div class="info-value">{{ purchaseOrder.notes }}</div>
                </div>
              </div>
            </div>

            <!-- CREATE MODE -->
            <form v-else class="po-form" @submit.prevent="submit">
              <div class="form-row">
                <div class="form-group full-width">
                  <label for="po-supplier">Supplier</label>
                  <input
                    id="po-supplier"
                    v-model="form.supplierName"
                    type="text"
                    placeholder="Supplier name"
                    class="form-input"
                    required
                  />
                </div>
              </div>

              <div class="form-row">
                <div class="form-group">
                  <label for="po-quantity">Quantity</label>
                  <input
                    id="po-quantity"
                    v-model.number="form.quantity"
                    type="number"
                    min="1"
                    class="form-input"
                    required
                  />
                </div>
                <div class="form-group">
                  <label for="po-unit-cost">Unit Cost</label>
                  <input
                    id="po-unit-cost"
                    v-model.number="form.unitCost"
                    type="number"
                    min="0"
                    step="0.01"
                    class="form-input"
                    required
                  />
                </div>
                <div class="form-group">
                  <label for="po-delivery">Expected Delivery</label>
                  <input
                    id="po-delivery"
                    v-model="form.expectedDeliveryDate"
                    type="date"
                    :min="today"
                    class="form-input"
                    required
                  />
                </div>
              </div>

              <div class="form-row">
                <div class="form-group full-width">
                  <label for="po-notes">Notes (optional)</label>
                  <textarea
                    id="po-notes"
                    v-model="form.notes"
                    rows="2"
                    placeholder="Anything the supplier should know"
                    class="form-input"
                  ></textarea>
                </div>
              </div>

              <div class="total-row">
                <span class="total-label">Total</span>
                <span class="total-value">{{ formatCurrency(estimatedTotal) }}</span>
              </div>

              <div v-if="submitError" class="error">{{ submitError }}</div>
            </form>
          </div>

          <div class="modal-footer">
            <button class="btn-secondary" type="button" @click="close">
              {{ isViewMode ? 'Close' : 'Cancel' }}
            </button>
            <button
              v-if="!isViewMode"
              class="btn-primary"
              type="button"
              :disabled="!canSubmit || submitting"
              @click="submit"
            >
              {{ submitting ? 'Creating...' : 'Create Purchase Order' }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script>
import { ref, computed, reactive, watch } from 'vue'
import { api } from '../api'
import { useI18n } from '../composables/useI18n'

export default {
  name: 'PurchaseOrderModal',
  props: {
    isOpen: {
      type: Boolean,
      default: false
    },
    backlogItem: {
      type: Object,
      default: null
    },
    mode: {
      type: String,
      default: 'create'
    }
  },
  emits: ['close', 'po-created'],
  setup(props, { emit }) {
    const { translateProductName, currentCurrency } = useI18n()

    const isViewMode = computed(() => props.mode === 'view')
    const currencySymbol = computed(() => (currentCurrency.value === 'JPY' ? '¥' : '$'))

    const loading = ref(false)
    const loadError = ref(null)
    const purchaseOrder = ref(null)

    const submitting = ref(false)
    const submitError = ref(null)

    const form = reactive({
      supplierName: '',
      quantity: 0,
      unitCost: null,
      expectedDeliveryDate: '',
      notes: ''
    })

    const today = computed(() => new Date().toISOString().slice(0, 10))

    const shortage = computed(() => {
      if (!props.backlogItem) return 0
      return props.backlogItem.quantity_needed - props.backlogItem.quantity_available
    })

    const estimatedTotal = computed(() => (form.quantity || 0) * (form.unitCost || 0))

    const canSubmit = computed(() =>
      form.supplierName.trim() !== '' &&
      form.quantity > 0 &&
      form.unitCost !== null &&
      form.unitCost >= 0 &&
      form.expectedDeliveryDate !== ''
    )

    const formatCurrency = (value) => {
      return currencySymbol.value + (Number(value) || 0).toLocaleString(undefined, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      })
    }

    const formatDate = (dateString) => {
      if (!dateString) return 'N/A'
      const date = new Date(dateString)
      // Guard against malformed dates from the API rather than rendering "Invalid Date"
      if (isNaN(date.getTime())) return 'N/A'
      return date.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })
    }

    const resetForm = () => {
      // Default the order to exactly the shortage: that is the quantity the
      // backlog item needs to clear, and it is what the user would type anyway.
      form.supplierName = ''
      form.quantity = shortage.value
      form.unitCost = null
      form.expectedDeliveryDate = ''
      form.notes = ''
      submitError.value = null
    }

    const loadPurchaseOrder = async () => {
      loading.value = true
      loadError.value = null
      purchaseOrder.value = null
      try {
        purchaseOrder.value = await api.getPurchaseOrderByBacklogItem(props.backlogItem.id)
      } catch (err) {
        loadError.value = err.response?.status === 404
          ? 'No purchase order has been raised for this item yet.'
          : 'Failed to load the purchase order'
        console.error('Failed to load purchase order:', err)
      } finally {
        loading.value = false
      }
    }

    // Re-prime on every open: the same modal instance is reused for whichever
    // backlog row was clicked, so stale form values would otherwise carry over.
    watch(
      () => [props.isOpen, props.backlogItem, props.mode],
      () => {
        if (!props.isOpen || !props.backlogItem) return
        if (isViewMode.value) {
          loadPurchaseOrder()
        } else {
          resetForm()
        }
      },
      { immediate: true }
    )

    const close = () => {
      emit('close')
    }

    const submit = async () => {
      if (!canSubmit.value || submitting.value) return

      submitting.value = true
      submitError.value = null
      try {
        const created = await api.createPurchaseOrder({
          backlog_item_id: props.backlogItem.id,
          supplier_name: form.supplierName.trim(),
          quantity: form.quantity,
          unit_cost: form.unitCost,
          expected_delivery_date: form.expectedDeliveryDate,
          notes: form.notes.trim() || null
        })
        emit('po-created', created)
      } catch (err) {
        submitError.value = err.response?.data?.detail || 'Failed to create the purchase order'
        console.error('Failed to create purchase order:', err)
      } finally {
        submitting.value = false
      }
    }

    return {
      translateProductName,
      isViewMode,
      loading,
      loadError,
      purchaseOrder,
      submitting,
      submitError,
      form,
      today,
      shortage,
      estimatedTotal,
      canSubmit,
      formatCurrency,
      formatDate,
      close,
      submit
    }
  }
}
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  padding: 1rem;
}

.modal-container {
  background: white;
  border-radius: 12px;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.15);
  max-width: 700px;
  width: 100%;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.5rem;
  border-bottom: 1px solid #e2e8f0;
}

.modal-title {
  font-size: 1.25rem;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.025em;
}

.close-button {
  background: none;
  border: none;
  color: #64748b;
  cursor: pointer;
  padding: 0.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  transition: all 0.15s ease;
}

.close-button:hover {
  background: #f1f5f9;
  color: #0f172a;
}

.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 2rem;
}

.item-header {
  display: flex;
  align-items: center;
  gap: 1.25rem;
  padding-bottom: 1.25rem;
  border-bottom: 1px solid #e2e8f0;
  margin-bottom: 1.25rem;
}

.item-title-section {
  flex: 1;
  min-width: 0;
}

.item-name {
  font-size: 1.375rem;
  font-weight: 700;
  color: #0f172a;
  margin: 0 0 0.375rem 0;
}

.item-sku {
  font-size: 0.875rem;
  color: #64748b;
  font-family: 'Monaco', 'Courier New', monospace;
}

.priority-badge {
  padding: 0.5rem 1rem;
  border-radius: 6px;
  font-size: 0.875rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.025em;
  flex-shrink: 0;
}

.priority-badge.high {
  background: #fecaca;
  color: #991b1b;
}

.priority-badge.medium {
  background: #fed7aa;
  color: #92400e;
}

.priority-badge.low {
  background: #dbeafe;
  color: #1e40af;
}

.shortage-banner {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  padding: 1rem 1.25rem;
  border: 2px solid #fecaca;
  background: #fef2f2;
  border-radius: 10px;
  margin-bottom: 1.5rem;
}

.shortage-label {
  font-size: 0.813rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #64748b;
}

.shortage-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: #dc2626;
}

.po-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.form-row {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
  flex: 1;
  min-width: 160px;
}

.form-group.full-width {
  flex-basis: 100%;
}

.form-group label {
  font-size: 0.813rem;
  font-weight: 600;
  color: #475569;
}

.form-input {
  padding: 0.625rem 0.75rem;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  font-size: 0.875rem;
  font-family: inherit;
  color: #0f172a;
  background: white;
  transition: border-color 0.15s ease;
}

.form-input:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.12);
}

textarea.form-input {
  resize: vertical;
}

.total-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  padding-top: 1rem;
  border-top: 1px solid #e2e8f0;
}

.total-label {
  font-size: 0.813rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #64748b;
}

.total-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: #0f172a;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1.5rem;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.info-item.full-width {
  grid-column: 1 / -1;
}

.info-label {
  font-size: 0.813rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #64748b;
}

.info-value {
  font-size: 0.938rem;
  color: #0f172a;
  font-weight: 500;
}

.info-value.strong {
  font-weight: 700;
}

.info-value.po-id {
  font-family: 'Monaco', 'Courier New', monospace;
  color: #2563eb;
}

.modal-footer {
  padding: 1.5rem;
  border-top: 1px solid #e2e8f0;
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
}

.btn-secondary {
  padding: 0.625rem 1.25rem;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-weight: 500;
  font-size: 0.875rem;
  color: #334155;
  cursor: pointer;
  transition: all 0.15s ease;
  font-family: inherit;
}

.btn-secondary:hover {
  background: #e2e8f0;
  border-color: #cbd5e1;
}

.btn-primary {
  padding: 0.625rem 1.25rem;
  background: #3b82f6;
  border: none;
  border-radius: 8px;
  font-weight: 600;
  font-size: 0.875rem;
  color: white;
  cursor: pointer;
  transition: background 0.15s ease;
  font-family: inherit;
}

.btn-primary:hover:not(:disabled) {
  background: #2563eb;
}

.btn-primary:disabled {
  background: #cbd5e1;
  cursor: not-allowed;
}

/* Modal transition animations */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-active .modal-container,
.modal-leave-active .modal-container {
  transition: transform 0.2s ease;
}

.modal-enter-from .modal-container,
.modal-leave-to .modal-container {
  transform: scale(0.95);
}
</style>
