<template>
  <div class="restocking">
    <div class="page-header">
      <h2>{{ t('restocking.title') }}</h2>
      <p>{{ t('restocking.description') }}</p>
    </div>

    <div v-if="loading && !hasLoaded" class="loading">{{ t('common.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else>
      <div class="card budget-card">
        <div class="budget-row">
          <div class="budget-label-group">
            <label class="budget-label" for="budget-slider">{{ t('restocking.budget.label') }}</label>
            <p class="budget-hint">{{ t('restocking.budget.hint') }}</p>
          </div>
          <div class="budget-value">{{ formatCurrency(budget) }}</div>
        </div>
        <div class="budget-slider-row">
          <input
            id="budget-slider"
            v-model.number="budget"
            type="range"
            min="0"
            :max="sliderMax"
            step="100"
            class="budget-slider"
            @input="onBudgetChange"
          />
          <button class="cover-all-btn" type="button" @click="coverEverything">
            {{ t('restocking.budget.coverAll') }}
          </button>
        </div>
      </div>

      <div v-if="successMessage" class="success-banner">{{ successMessage }}</div>
      <div v-if="submitError" class="error">{{ submitError }}</div>

      <div class="stats-grid">
        <div class="stat-card info">
          <div class="stat-label">{{ t('restocking.summary.allocated') }}</div>
          <div class="stat-value">{{ formatCurrency(totalCost) }}</div>
        </div>
        <div class="stat-card success">
          <div class="stat-label">{{ t('restocking.summary.remaining') }}</div>
          <div class="stat-value">{{ formatCurrency(remainingBudget) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('restocking.summary.itemsSelected') }}</div>
          <div class="stat-value">{{ recommendedItems.length }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('restocking.summary.totalUnits') }}</div>
          <div class="stat-value">{{ totalUnits.toLocaleString() }}</div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.recommended.title') }} ({{ recommendedItems.length }})</h3>
          <button
            class="place-order-btn"
            type="button"
            :disabled="recommendedItems.length === 0 || submitting"
            @click="placeOrder"
          >
            {{ submitting ? t('restocking.placing') : t('restocking.placeOrder') }}
          </button>
        </div>

        <div v-if="recommendedItems.length === 0 && excludedItems.length === 0" class="empty-state">
          {{ t('restocking.recommended.allCovered') }}
        </div>
        <div v-else-if="recommendedItems.length === 0" class="empty-state">
          {{ t('restocking.recommended.empty') }}
        </div>
        <div v-else class="table-container">
          <table>
            <thead>
              <tr>
                <th>{{ t('restocking.table.sku') }}</th>
                <th>{{ t('restocking.table.item') }}</th>
                <th>{{ t('restocking.table.category') }}</th>
                <th>{{ t('restocking.table.warehouse') }}</th>
                <th>{{ t('restocking.table.trend') }}</th>
                <th>{{ t('restocking.table.onHand') }}</th>
                <th>{{ t('restocking.table.reorderPoint') }}</th>
                <th>{{ t('restocking.table.forecast') }}</th>
                <th>{{ t('restocking.table.quantity') }}</th>
                <th>{{ t('restocking.table.unitCost') }}</th>
                <th>{{ t('restocking.table.lineCost') }}</th>
                <th>{{ t('restocking.table.leadTime') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in recommendedItems" :key="item.sku">
                <td>
                  <strong>{{ item.sku }}</strong>
                  <span v-if="item.below_reorder_point" class="badge danger reorder-badge">
                    {{ t('restocking.belowReorderPoint') }}
                  </span>
                </td>
                <td>{{ translateProductName(item.name) }}</td>
                <td>{{ item.category }}</td>
                <td>{{ translateWarehouse(item.warehouse) }}</td>
                <td>
                  <span :class="['badge', item.trend]">{{ t(`trends.${item.trend}`) }}</span>
                </td>
                <td>{{ item.quantity_on_hand.toLocaleString() }}</td>
                <td>{{ item.reorder_point.toLocaleString() }}</td>
                <td>{{ item.forecasted_demand.toLocaleString() }}</td>
                <td>{{ item.recommended_quantity.toLocaleString() }}</td>
                <td>{{ formatCurrency(item.unit_cost) }}</td>
                <td><strong>{{ formatCurrency(item.line_cost) }}</strong></td>
                <td>{{ t('orders.submitted.leadTimeDays', { days: item.lead_time_days }) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div v-if="excludedItems.length > 0" class="card excluded-card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.excluded.title') }} ({{ excludedItems.length }})</h3>
        </div>
        <p class="excluded-description">{{ t('restocking.excluded.description') }}</p>
        <div class="table-container">
          <table class="excluded-table">
            <thead>
              <tr>
                <th>{{ t('restocking.table.sku') }}</th>
                <th>{{ t('restocking.table.item') }}</th>
                <th>{{ t('restocking.table.warehouse') }}</th>
                <th>{{ t('restocking.table.quantity') }}</th>
                <th>{{ t('restocking.table.lineCost') }}</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in excludedItems" :key="item.sku">
                <td>{{ item.sku }}</td>
                <td>{{ translateProductName(item.name) }}</td>
                <td>{{ translateWarehouse(item.warehouse) }}</td>
                <td>{{ item.recommended_quantity.toLocaleString() }}</td>
                <td>{{ formatCurrency(item.line_cost) }}</td>
                <td class="needed-cell">{{ t('restocking.excluded.needed', { amount: formatCurrency(amountNeeded(item)) }) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { api } from '../api'
import { useI18n } from '../composables/useI18n'

export default {
  name: 'Restocking',
  setup() {
    const { t, currentCurrency, translateProductName, translateWarehouse } = useI18n()

    const currencySymbol = computed(() => (currentCurrency.value === 'JPY' ? '¥' : '$'))

    const loading = ref(true)
    // Only the very first load blanks the page. Later reloads keep the slider mounted,
    // otherwise every debounced budget change would rip it out from under the cursor.
    const hasLoaded = ref(false)
    const error = ref(null)
    const submitting = ref(false)
    const submitError = ref(null)
    const successMessage = ref(null)

    const budget = ref(7000)
    const maxUsefulBudget = ref(0)
    const totalCost = ref(0)
    const remainingBudget = ref(0)
    const recommendedItems = ref([])
    const excludedItems = ref([])

    // Round the slider ceiling up to a clean multiple of 100 so the handle
    // never sits mid-step; fall back to a sane default before the first load.
    const sliderMax = computed(() => {
      if (!maxUsefulBudget.value) return 20000
      return Math.ceil(maxUsefulBudget.value / 100) * 100
    })

    const totalUnits = computed(() =>
      recommendedItems.value.reduce((sum, item) => sum + item.recommended_quantity, 0)
    )

    // Keep up to 2 decimals: unit costs carry cents ($12.50, $8.75) and rounding them
    // to whole units misstates the price the order is actually placed at.
    const formatCurrency = (value) => {
      return currencySymbol.value + (Number(value) || 0).toLocaleString(undefined, {
        minimumFractionDigits: 0,
        maximumFractionDigits: 2
      })
    }

    // How much more budget an excluded item would need to fit, based on
    // what's left over after covering the recommended items.
    const amountNeeded = (item) => {
      const shortfall = item.line_cost - remainingBudget.value
      return shortfall > 0 ? shortfall : item.line_cost
    }

    const loadRecommendations = async (value) => {
      loading.value = true
      error.value = null
      try {
        const data = await api.getRestockingRecommendations(value)
        maxUsefulBudget.value = data.max_useful_budget
        totalCost.value = data.total_cost
        remainingBudget.value = data.remaining_budget
        recommendedItems.value = data.recommended_items
        excludedItems.value = data.excluded_items
      } catch (err) {
        error.value = 'Failed to load restocking recommendations'
        console.error(err)
      } finally {
        loading.value = false
        hasLoaded.value = true
      }
    }

    // Manual debounce (no @vueuse dependency): wait for the slider to settle
    // for 300ms before firing the API call, so dragging doesn't spam requests.
    let debounceTimer = null
    const onBudgetChange = () => {
      successMessage.value = null
      submitError.value = null
      clearTimeout(debounceTimer)
      debounceTimer = setTimeout(() => {
        loadRecommendations(budget.value)
      }, 300)
    }

    const coverEverything = () => {
      // Round up to the slider's step, otherwise the thumb snaps to a different value
      // than the label shows and the budget reads as an odd figure like $18,338.4.
      budget.value = Math.ceil(maxUsefulBudget.value / 100) * 100
      onBudgetChange()
    }

    const placeOrder = async () => {
      if (recommendedItems.value.length === 0 || submitting.value) return

      submitting.value = true
      submitError.value = null
      successMessage.value = null
      try {
        const items = recommendedItems.value.map((item) => ({
          sku: item.sku,
          name: item.name,
          quantity: item.recommended_quantity,
          unit_price: item.unit_cost
        }))
        const order = await api.createRestockingOrder({ items, budget: budget.value })
        successMessage.value = t('restocking.success', {
          orderNumber: order.order_number,
          days: order.lead_time_days
        })
        await loadRecommendations(budget.value)
      } catch (err) {
        submitError.value = t('restocking.error')
        console.error(err)
      } finally {
        submitting.value = false
      }
    }

    onMounted(() => loadRecommendations(budget.value))
    onBeforeUnmount(() => clearTimeout(debounceTimer))

    return {
      t,
      translateProductName,
      translateWarehouse,
      loading,
      hasLoaded,
      error,
      submitting,
      submitError,
      successMessage,
      budget,
      totalCost,
      remainingBudget,
      recommendedItems,
      excludedItems,
      sliderMax,
      totalUnits,
      formatCurrency,
      amountNeeded,
      onBudgetChange,
      coverEverything,
      placeOrder
    }
  }
}
</script>

<style scoped>
.budget-card {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.budget-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
}

.budget-label-group {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.budget-label {
  font-size: 0.938rem;
  font-weight: 700;
  color: #0f172a;
}

.budget-hint {
  font-size: 0.813rem;
  color: #64748b;
}

.budget-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: #0f172a;
  white-space: nowrap;
}

.budget-slider-row {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.budget-slider {
  flex: 1;
  accent-color: #3b82f6;
}

.cover-all-btn {
  padding: 0.5rem 1rem;
  border-radius: 6px;
  border: 1px solid #cbd5e1;
  background: white;
  color: #334155;
  font-weight: 600;
  font-size: 0.875rem;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.15s ease;
}

.cover-all-btn:hover {
  border-color: #3b82f6;
  color: #2563eb;
  background: #eff6ff;
}

.place-order-btn {
  padding: 0.5rem 1.25rem;
  border-radius: 6px;
  border: none;
  background: #3b82f6;
  color: white;
  font-weight: 600;
  font-size: 0.875rem;
  cursor: pointer;
  transition: background 0.15s ease;
}

.place-order-btn:hover:not(:disabled) {
  background: #2563eb;
}

.place-order-btn:disabled {
  background: #cbd5e1;
  cursor: not-allowed;
}

.success-banner {
  background: #d1fae5;
  border: 1px solid #6ee7b7;
  color: #065f46;
  padding: 1rem;
  border-radius: 8px;
  margin-bottom: 1.25rem;
  font-size: 0.938rem;
  font-weight: 500;
}

.empty-state {
  padding: 2rem;
  text-align: center;
  color: #64748b;
  font-size: 0.938rem;
}

.reorder-badge {
  margin-left: 0.5rem;
}

.excluded-card {
  opacity: 0.85;
}

.excluded-description {
  color: #64748b;
  font-size: 0.875rem;
  margin-bottom: 0.75rem;
}

.excluded-table {
  color: #64748b;
}
</style>
